"""系统初始化与演示数据播种（幂等）。

- light 模式（SEED_DEMO_DATA=0）：仅账号、59 件商品、9 个 Agent 注册记录（剧本/pytest 使用，快速确定）。
- 完整模式（默认）：额外播种历史订单/议价/评价/审计，以及真实 LangGraph 演示流程
  （veto/人工复核/待支付/风险终裁/纠纷终裁等待中 + C1/C2/C6/C8 历史事件），
  使「我的商品」「我的订单」与 Agent 控制台首次打开即有丰富真实数据。
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, or_, select

from app.core.config import settings
from app.core.database import engine
from app.models import (
    AgentStatus,
    Appeal,
    Item,
    Negotiation,
    Offer,
    Order,
    Review,
    User,
)

DEMO_PASSWORD = "123456"

# student_no, nickname, current_credit, risk_tag, avatar_seed, status(可选)
USERS: list[dict] = [
    {"student_no": "2400320321", "nickname": "梁奕琦", "is_admin": True, "credit": 100, "risk_tag": "normal", "avatar_seed": "LYQ"},
    {"student_no": "20240001", "nickname": "张学长", "is_admin": False, "credit": 104, "risk_tag": "normal", "avatar_seed": "ZXZ"},
    {"student_no": "20240002", "nickname": "李学姐", "is_admin": False, "credit": 100, "risk_tag": "normal", "avatar_seed": "LXJ"},
    {"student_no": "20240003", "nickname": "王同学", "is_admin": False, "credit": 102, "risk_tag": "normal", "avatar_seed": "WTX"},
    {"student_no": "20240004", "nickname": "赵一鸣", "is_admin": False, "credit": 106, "risk_tag": "normal", "avatar_seed": "ZYM"},
    {"student_no": "20240005", "nickname": "钱多多", "is_admin": False, "credit": 104, "risk_tag": "normal", "avatar_seed": "QDD"},
    {"student_no": "20240006", "nickname": "风险买家", "is_admin": False, "credit": 68, "risk_tag": "high_risk", "avatar_seed": "FXM"},
    {"student_no": "20240007", "nickname": "孙七", "is_admin": False, "credit": 75, "risk_tag": "high_risk", "avatar_seed": "SQ"},
    # 冻结账号：禁止交易类操作但保留登录/浏览/申诉权（FR-1），带真实历史纠纷待办
    {"student_no": "20240008", "nickname": "冻结账号", "is_admin": False, "credit": 55,
     "risk_tag": "high_risk", "avatar_seed": "DJZ", "status": "frozen"},
    # V5 AI 虚拟用户（FR-201）：可登录的 AI 卖家/AI 买家，密码同为 DEMO_PASSWORD
    {"student_no": "AI10001", "nickname": "AI校园摊主", "is_admin": False, "credit": 102,
     "risk_tag": "normal", "avatar_seed": "AIS", "is_ai": True,
     "ai_persona": "大四数码&教材摊主，爽快好说话，可小刀，成交爽快"},
    {"student_no": "AI10002", "nickname": "AI同学小北", "is_admin": False, "credit": 98,
     "risk_tag": "normal", "avatar_seed": "AIB", "is_ai": True,
     "ai_persona": "大一新生买家，预算有限，喜欢礼貌砍价"},
]

# (seller_no, title, category, condition, price, suggest_min, suggest_max,
#  status, image, description)
def _img(name: str) -> str:
    return f"/images/items/{name}.jpg"


ITEMS: list[tuple] = [
    # ---------- 在售商品 1-19（ID 顺序固定，测试依赖前 10）----------
    ("20240001", "高等数学（第七版）上册", "教材资料", "八成新", 18.0, 15.0, 22.0, "on_sale", _img("item-math"),
     "同济大学高等数学教材，上课用了一学期，前两章有少量铅笔笔记，不影响阅读，书角微卷。"),
    ("20240002", "考研英语历年真题精讲 2010-2024", "教材资料", "九成新", 35.0, 30.0, 45.0, "on_sale", _img("item-english"),
     "考研英语真题集，答案解析完整，只有前几套做过，后面全新，附赠单词小册。"),
    ("20240002", "线性代数辅导讲义 李永乐", "教材资料", "八成新", 12.0, 10.0, 16.0, "on_sale", _img("item-linear"),
     "李永乐线代讲义，经典考研参考书，例题有标注，附送自己整理的矩阵笔记两页。"),
    ("20240002", "索尼 WH-CH520 无线头戴耳机 黑色", "数码电子", "九成新", 180.0, 160.0, 210.0, "on_sale", _img("item-headphone"),
     "去年双十一购入，使用不到十次，耳罩无磨损，续航依旧很顶，配件齐全带原包装。"),
    ("20240003", "罗技 M330 无线静音鼠标", "数码电子", "八成新", 45.0, 38.0, 55.0, "on_sale", _img("item-mouse"),
     "静音点击，图书馆神器，含原装接收器和一节新电池，外观正常使用痕迹。"),
    ("20240003", "宿舍护眼台灯 三档调光 USB 充电", "生活用品", "九成新", 25.0, 20.0, 32.0, "on_sale", _img("item-lamp"),
     "折叠便携护眼灯，三档色温，USB 充电续航持久，底座 1/2/3 触控按键灵敏。"),
    ("20240003", "桌面收纳置物架 三层 白色", "生活用品", "九成新", 20.0, 15.0, 28.0, "on_sale", _img("item-rack"),
     "白框木板三层置物架，放书本化妆品都合适，毕业搬家便宜出，可拆卸。"),
    ("20240003", "斯伯丁篮球 PU 7号球 室外款", "运动户外", "八成新", 55.0, 45.0, 70.0, "on_sale", _img("item-basketball"),
     "室外水泥地打了一学期，表皮轻微磨损但手感和气密性都正常，送气针球网。"),
    ("20240003", "小米台灯1S 米家智能调光", "生活用品", "九成新", 60.0, 50.0, 75.0, "on_sale", _img("item-milamp"),
     "支持米家 App 与小爱同学调光，灯臂多角度可调，无频闪护眼，包装盒还在。"),
    ("20240003", "大学物理实验报告与期末真题", "教材资料", "九成新", 8.0, 6.0, 12.0, "on_sale", _img("item-physics"),
     "大物实验报告模板+本校近五年期末真题与详细解答，实验数据可参考。"),
    ("20240001", "Apple iPad 9代 64G 深空灰", "数码电子", "九成新", 1650.0, 1500.0, 1850.0, "on_sale", _img("item-ipad"),
     "自用 iPad 第九代，无拆无修无磕碰，电池健康 92%，送钢化膜与保护壳，适合网课笔记。"),
    ("20240001", "肖秀荣考研政治知识点精讲精练", "教材资料", "八五新", 28.0, 22.0, 35.0, "on_sale", _img("item-politics"),
     "考研政治复习全书，重点章节有荧光笔标注，附赠徐涛小黄书与思维导图打印版。"),
    ("20240002", "Kindle Paperwhite 4 电子书阅读器 8G", "数码电子", "九成新", 320.0, 280.0, 380.0, "on_sale", _img("item-kindle"),
     "Paperwhite 四代，屏幕无划痕无残影，背光均匀，登录自己账号即可，送数据线。"),
    ("20240002", "佳能 IXUS 复古卡片数码相机", "数码电子", "八成新", 260.0, 220.0, 320.0, "on_sale", _img("item-camera"),
     "CCD 复古画质，随手拍很有胶片感，功能完好，电池充电器齐全，机身轻微使用痕迹。"),
    ("20240003", "捷安特 ATX 山地自行车 21速", "运动户外", "八成新", 480.0, 420.0, 560.0, "on_sale", _img("item-bike"),
     "通勤代步神车，21 速变速顺畅，碟刹灵敏，刚做过保养换了新车胎，校内看车。"),
    ("20240003", "卡西欧 fx-991CN X 科学函数计算器", "教材资料", "九成新", 55.0, 48.0, 68.0, "on_sale", _img("item-calculator"),
     "考研/高数考试专用计算器，中文菜单，按键灵敏，屏幕无坏点，含保护盖。"),
    ("20240001", "优衣库摇粒绒抓绒外套 藏蓝 L", "服饰鞋包", "九成新", 79.0, 65.0, 99.0, "on_sale", _img("item-jacket"),
     "藏青色 L 码，冬天自习室保暖神器，无起球无污渍，机洗不变形。"),
    ("20240002", "膳魔师保温杯 500ml 哑光黑", "生活用品", "九五新", 65.0, 55.0, 80.0, "on_sale", _img("item-thermos"),
     "保温 12 小时以上，哑光黑耐脏，健身房/上课都适用，内胆无异味无磕碰。"),
    ("20240003", "雅马哈 F310 入门民谣木吉他", "其他", "八成新", 420.0, 360.0, 480.0, "on_sale", _img("item-guitar"),
     "新手入门神器，音准稳定，琴颈笔直，换过一套新弦，送琴包拨片变调夹。"),
    # ---------- 历史商品 20-32（已成交/下架/驳回/冻结）----------
    ("20240003", "宿舍遮光床帘 星星藏青加厚款", "生活用品", "九成新", 35.0, 30.0, 42.0, "dealed", _img("item-curtain"),
     "加厚遮光布，星星图案，上铺专用三片式，遮光效果好，毕业出。"),
    ("20240001", "考研数学复习全书（含详细笔记）", "教材资料", "八五新", 22.0, 18.0, 28.0, "dealed", _img("item-mathreview"),
     "李王复习全书，数一全套，错题与技巧笔记非常详细，考研党直接接手。"),
    ("20240002", "耳机数据线硬壳收纳包", "数码电子", "九成新", 15.0, 10.0, 20.0, "dealed", _img("item-earbudcase"),
     "抗震硬壳小包，收纳耳机 U 盘数据线，拉链顺滑，内部分隔完好。"),
    ("20240003", "折叠床上小书桌 杯托款", "生活用品", "八成新", 32.0, 26.0, 40.0, "locked", _img("item-bedtable"),
     "床上懒人桌，带杯托与卡槽，桌腿可折叠，承重稳，上铺学习必备。"),
    ("20240002", "大学英语四六级真题套卷", "教材资料", "八成新", 18.0, 14.0, 24.0, "locked", _img("item-cet"),
     "四六级历年真题两套合售，听力材料齐全，部分已做，答案解析完整。"),
    ("20240001", "马卡龙笔记本四本装（含中性笔）", "生活用品", "全新", 12.0, 10.0, 18.0, "locked", _img("item-notebookset"),
     "四色 B5 笔记本全新未拆，附两支按动中性笔，开学囤多了。"),
    ("20240002", "87键青轴机械键盘 蓝光版", "数码电子", "九成新", 89.0, 75.0, 110.0, "locked", _img("item-keyboard"),
     "国产 87 键青轴，冰蓝背光，码字清脆，换键盘故出，功能全好。"),
    ("20240003", "TPE 瑜伽垫 加厚 8mm 紫色", "运动户外", "九五新", 25.0, 20.0, 35.0, "on_sale", _img("item-yogamat"),
     "防滑加厚瑜伽垫，用过两次几乎全新，含绑带，宿舍健身拉伸用。"),
    ("20240001", "小米充电宝 10000mAh 双向快充", "数码电子", "九成新", 45.0, 38.0, 58.0, "dealed", _img("item-powerbank"),
     "双向快充版，容量实标无鼓包，外壳轻微划痕，送 Type-C 短线。"),
    ("20240003", "防滑晾衣架 10个装 蓝色", "生活用品", "九成新", 10.0, 8.0, 15.0, "locked", _img("item-hanger"),
     "加粗防滑衣架 10 个，承重力好，无痕衣肩，打包一起出。"),
    ("20240001", "电路原理（旧版电气工程教材）", "教材资料", "七成新", 15.0, 10.0, 22.0, "off_shelf", _img("item-electrical"),
     "旧版电路原理，内容经典但笔记较多，暂时下架留着自用。"),
    ("20240002", "老式护眼台灯（底座掉漆）", "生活用品", "五成新", 8.0, 5.0, 12.0, "rejected", _img("item-oldlamp"),
     "老式台灯，底座掉漆、灯颈略松，不影响照明。"),
    ("20240003", "热得快电热棒 3000W 大功率", "生活用品", "七成新", 10.0, None, None, "frozen", _img("item-rod"),
     "宿舍烧水很快的热得快，大功率加热棒，带电源线。"),
    # ---------- 冻结账号（20240008）在售商品 33-34 ----------
    ("20240008", "雷蛇炼狱蝰蛇标准有线游戏鼠标", "数码电子", "八成新", 38.0, 32.0, 48.0, "on_sale", _img("item-mouse"),
     "自用游戏鼠标，按键回弹清脆无双击，侧键正常，线材无破损，脚贴轻微磨损，包装盒不在了。"),
    ("20240008", "达尔优 EK815 机械键盘 青轴 87键", "数码电子", "八成新", 59.0, 50.0, 75.0, "on_sale", _img("item-keyboard"),
     "青轴手感段落感强，全键触发正常无臭轴，键帽微油光，送拔键器和备用轴体两颗。"),
    # ---------- 历史订单配套商品 35-37（买家：冻结账号/赵一鸣）----------
    ("20240002", "森海塞尔 MX375 入耳式有线耳机", "数码电子", "九成新", 69.0, 58.0, 85.0, "locked", _img("item-headphone"),
     "经典平头塞，三频均衡，线材柔软无发硬，3.5mm 插头接触良好，带原装硅胶收纳袋。"),
    ("20240002", "新东方六级真题词汇（乱序版）", "教材资料", "八成新", 16.0, 12.0, 22.0, "on_sale", _img("item-cet"),
     "六级备考词汇书，前三十页有铅笔标注，其余空白，书签完整，取消订单后重新上架。"),
    ("20240001", "Apple Pencil 第一代（含备用笔尖）", "数码电子", "九成新", 450.0, 400.0, 520.0, "dealed", _img("item-ipad"),
     "iPad 手写笔第一代，压感倾斜均正常，无拆修，lightning 转接器与备用笔尖齐全，已成交。"),
    # ---------- V5 T4-1：AI 校园摊主在售 38-45（8 件，数码/教材/生活/运动/服饰多类目）----------
    ("AI10001", "AOC 24英寸 IPS 显示器 低蓝光可壁挂", "数码电子", "九成新", 450.0, 400.0, 520.0, "on_sale", _img("item-monitor"),
     "毕业出显示器，24 寸 IPS 屏色彩正常无坏点，送 HDMI 线和电源适配器，支架可俯仰调节，写代码看网课都合适。"),
    ("AI10001", "达尔优 EK815 机械键盘 87键 红轴", "数码电子", "九成新", 95.0, 80.0, 120.0, "on_sale", _img("item-keyboard"),
     "红轴码字安静不扰民，87 键省桌面，冰蓝背光，键帽无打油，换了配列键盘所以出，功能全好可当面试。"),
    ("AI10001", "考研政治+英语复习资料一堆（肖秀荣/黄皮书）", "教材资料", "八成新", 48.0, 38.0, 65.0, "on_sale", _img("item-textbook2"),
     "上岸清书：肖四肖八、知识点精讲、英语黄皮书真题一摞打包，部分有铅笔标注，重难点已折页，打包带走最划算。"),
    ("AI10001", "简约白色保温杯 450ml 316不锈钢", "生活用品", "九五新", 28.0, 22.0, 38.0, "on_sale", _img("item-watercup"),
     "白色哑光杯身，316 内胆好清洗，装开水一上午还烫嘴，杯底无磕碰，买了新杯子这个闲置，袋装好带走。"),
    ("AI10001", "深蓝大容量双肩包 15.6寸防震电脑仓", "服饰鞋包", "九成新", 55.0, 45.0, 75.0, "on_sale", _img("item-backpack"),
     "深蓝色耐脏，独立防震电脑仓装得下 15.6 寸笔记本，侧袋放水杯雨伞，拉链顺滑背带不塌，实习通勤都能背。"),
    ("AI10001", "碳素纤维双拍羽毛球拍对拍套装", "运动户外", "九成新", 38.0, 30.0, 50.0, "on_sale", _img("item-badminton"),
     "两支对拍送三个尼龙球和拍套，拍子轻好上手，拍线紧实无断裂，宿舍楼下约球拎起就走，新手练习足够。"),
    ("AI10001", "初学者尤克里里 23寸 桃花芯木", "生活用品", "九成新", 88.0, 70.0, 120.0, "on_sale", _img("item-ukulele"),
     "23 寸入门尤克里里，音准稳定弦距低不勒手，送琴包背带和备用弦，课余弹唱解压，换吉他了所以出。"),
    ("AI10001", "罗技 M280 无线鼠标 办公静音款", "数码电子", "九成新", 35.0, 28.0, 48.0, "on_sale", _img("item-mouse"),
     "手感贴合的办公小鼠，静音按键图书馆友好，接收器在电池仓里，送一节新电池，即插即用。"),
    # ---------- V5 T4-1：普通账号各补在售 46-51（含美妆个护）----------
    ("20240001", "联想小新 Pro14 轻薄笔记本 R7/16G/512G", "数码电子", "九成新", 2680.0, 2400.0, 3100.0, "on_sale", _img("item-laptop"),
     "银色金属机身很轻薄，配置写标题里了，日常网课剪 vlog 都流畅，无拆无修电池健康 89%，原装充电器在，可当面试机。"),
    ("20240002", "珀莱雅补水护肤礼盒（水乳精华全套）", "美妆个护", "全新", 79.0, 60.0, 110.0, "on_sale", _img("item-skincare"),
     "生日收到的套装，肤质不合适用不上，塑封都没拆，保质期到后年，礼盒装送人自用都合适，防伪可查。"),
    ("20240002", "漫步者 X2 真无线蓝牙耳机 白色", "数码电子", "九成新", 89.0, 75.0, 115.0, "on_sale", _img("item-earbuds2"),
     "白色半入耳戴着舒服，通话降噪上课接电话清楚，充电仓无划痕，耳塞套齐全，换新耳机便宜出。"),
    ("20240003", "西昊 M57 人体工学椅 网布带头枕", "生活用品", "八成新", 165.0, 135.0, 210.0, "on_sale", _img("item-chair"),
     "腰托扶手都可调，网布夏天不闷汗，久坐写论文救星，轮子顺滑无异响，搬校区带不走，仅限校内自提。"),
    ("20240004", "美洲狮直排轮滑鞋 42码 含护具", "运动户外", "八成新", 120.0, 95.0, 160.0, "on_sale", _img("item-skates"),
     "42 码黑蓝轮滑鞋，刀架稳固轮子顺滑，没刷过几次街，护具六件套和大号收纳包一起送，社团退坑出。"),
    ("20240005", "良品铺子零食大礼包 整箱未拆", "生活用品", "全新", 39.0, 30.0, 55.0, "on_sale", _img("item-snacks"),
     "活动凑单买多了，一整箱二十多包肉脯坚果辣条都有，日期新鲜，宿舍囤货团建分着吃划算，整箱不刀。"),
    # ---------- V5 T4-2：管理员商品 52-55（2 在售 + 1 已成交 + 1 已下架）----------
    ("2400320321", "漫步者 W820NB 头戴式蓝牙降噪耳机", "数码电子", "九成新", 159.0, 135.0, 195.0, "on_sale", _img("item-headphone"),
     "双金标版降噪头戴，自习室开降噪很安静，耳罩柔软不夹头，续航三十小时以上，原包装配件齐全，换新设备出。"),
    ("2400320321", "紫米 20000mAh 双向快充充电宝", "数码电子", "九成新", 69.0, 58.0, 90.0, "on_sale", _img("item-powerbank"),
     "两万毫安能充手机三四次，22.5W 双向快充，额度可带上飞机，外壳只有正常使用痕迹，接口不松动，送短线。"),
    ("2400320321", "RK 机械键盘 104键 茶轴（含皮质手托）", "数码电子", "九成新", 75.0, 60.0, 95.0, "dealed", _img("item-keyboard"),
     "104 键茶轴手感均衡，带数字区与白色背光，附赠皮质手托，已与买家面交成交。"),
    ("2400320321", "AOC 24英寸窄边框显示器（自用暂留）", "数码电子", "八五新", 380.0, 320.0, 460.0, "off_shelf", _img("item-monitor"),
     "24 寸窄边框显示器，当副屏写论文很顺手，最近宿舍整理暂时下架，屏幕无坏点无拆修。"),
    # ---------- V5 T4-2：新增历史订单配套商品 56-59 ----------
    ("20240001", "Apple iPad Air4 64G 玫瑰金（含二代笔）", "数码电子", "九成新", 2180.0, 1900.0, 2480.0, "dealed", _img("item-ipad"),
     "Air4 全面屏配二代笔，网课记笔记流畅，机身无磕碰无拆修，包装盒齐全，已与买家当面验机成交。"),
    ("20240002", "QCY H3 头戴式蓝牙降噪耳机 黑色", "数码电子", "九成新", 199.0, 168.0, 235.0, "locked", _img("item-headphone"),
     "黑色头戴蓝牙降噪，耳罩无掉皮，降噪与麦克风都正常，原盒配件齐全，买家已拍下等待面交。"),
    ("AI10001", "米家智能台灯 Pro 可折叠护眼", "生活用品", "九成新", 89.0, 75.0, 110.0, "locked", _img("item-lamp"),
     "多档色温亮度可调，灯臂可折叠省空间，无频闪护眼，买家已拍下，约时间宿舍楼下交付。"),
    ("AI10001", "小米 Buds 4 真无线降噪耳机 白色", "数码电子", "九成新", 119.0, 99.0, 150.0, "dealed", _img("item-earbuds2"),
     "白色真无线降噪，半入耳久戴不痛，充电仓无划痕，配件齐全，已与买家愉快成交。"),
]

AGENTS: list[dict] = [
    {"name": "coordinator", "display_name": "协调管理 Agent", "avatar": "Workflow",
     "accent": "#818CF8", "capabilities": ["流程编排", "冲突检测", "加权仲裁", "全局效用评分",
                                           "目标相容性检查", "SSOT 纠正", "熔断代管", "人工转接"],
     "description": "调度中枢与裁判长：主持加权投票与效用仲裁，检测四类冲突并三级升级，熔断异常 Agent 并规则代管。"},
    {"name": "user_agent", "display_name": "用户代理 Agent", "avatar": "UserRound",
     "accent": "#60A5FA", "capabilities": ["意图结构化", "用户画像", "保留价维护", "授权区间代客出价"],
     "description": "用户数字分身：解析自然语言意图，维护画像与保留价，在授权区间内代客出价，越界或成交前请求确认。"},
    {"name": "commodity", "display_name": "商品管理 Agent", "avatar": "Package",
     "accent": "#34D399", "capabilities": ["信息结构化", "类目成色识别", "建议定价", "上下架管理"],
     "description": "上架管家：结构化标准商品档案、建议价区间与未锁定商品的上下架管理。"},
    {"name": "moderation", "display_name": "内容审核 Agent", "avatar": "ShieldAlert",
     "accent": "#F87171", "capabilities": ["违禁审核", "规则模型双判定", "安全一票否决", "风险投票"],
     "description": "安检员：违禁/欺诈双判定三档处置并逐条给出依据，命中违禁行使不可覆盖的一票否决。"},
    {"name": "search", "display_name": "搜索推荐 Agent", "avatar": "SearchCheck",
     "accent": "#22D3EE", "capabilities": ["多条件检索", "相关性排序", "匹配理由", "偏向自检重排"],
     "description": "导购员：仅搜在售商品，综合相关性/成色/价格/信用排序并给出匹配理由，偏向佣金时接受纠偏重排。"},
    {"name": "negotiation", "display_name": "议价谈判 Agent", "avatar": "MessagesSquare",
     "accent": "#818CF8", "capabilities": ["多轮议价主持", "单调让步校验", "纳什参考价", "超时破裂推荐"],
     "description": "中立主持人：组织双边多轮出价、单调让步与纳什参考，超轮次/超时破裂并推荐同类。"},
    {"name": "order", "display_name": "交易履约 Agent", "avatar": "ClipboardList",
     "accent": "#FBBF24", "capabilities": ["订单状态机", "预占锁", "抢单三优先裁决", "模拟支付", "超时释放"],
     "description": "账房调度：预占锁建单、抢单三优先级裁决、沙箱支付与超时释放，守护订单状态机。"},
    {"name": "credit", "display_name": "信用评价 Agent", "avatar": "BadgeCheck",
     "accent": "#F472B6", "capabilities": ["风险意见", "双向评价聚合", "信用分动态更新", "裁决信用扣罚"],
     "description": "信用局：输出带置信度风险意见，聚合一单一次互评并动态更新信用分，执行裁决联动扣罚。"},
    {"name": "arbitrator", "display_name": "纠纷仲裁 Agent", "avatar": "Gavel",
     "accent": "#FB923C", "capabilities": ["证据链汇总", "规则库裁决", "结构化裁决书", "升级人工"],
     "description": "线上小法官：汇总全链路证据包，输出责任+依据+执行方案的结构化裁决书，超阈值升级人工。"},
]

# (buyer_no, seller_no, item_index(1-based), deal_price, status, buyer_review, seller_review, days_ago)
HISTORY_ORDERS: list[tuple] = [
    ("20240004", "20240003", 20, 32.0, "reviewed", 5, 5, 6),
    ("20240005", "20240001", 21, 20.0, "reviewed", 5, 5, 5),
    ("20240004", "20240002", 22, 12.0, "completed", None, 4, 3),
    ("20240005", "20240003", 23, 30.0, "receiving", None, None, 1),
    ("20240004", "20240002", 24, 16.0, "paid", None, None, 1),
    ("20240005", "20240001", 25, 10.0, "receiving", None, None, 1),
    ("20240004", "20240002", 26, 85.0, "unpaid", None, None, 0),
    ("20240005", "20240003", 27, 23.0, "canceled", None, None, 4),
    ("20240005", "20240001", 28, 42.0, "refunded", None, None, 2),
]

_bcrypt_cache: dict[str, str] = {}


def hash_password(raw: str) -> str:
    from app.core.security import hash_password as _h

    if raw not in _bcrypt_cache:
        _bcrypt_cache[raw] = _h(raw)
    return _bcrypt_cache[raw]


def _naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def run_seeds(light: bool = False) -> bool:
    """播种基础数据。返回 True 表示本次为全新播种（调用方可据此运行一次性演示流）。"""
    with Session(engine) as session:
        if session.exec(select(User).limit(1)).first():
            return False  # 已有数据，保持幂等

        # ---------------- 用户 ----------------
        user_map: dict[str, User] = {}
        for u in USERS:
            user = User(
                student_no=u["student_no"],
                password_hash=hash_password(DEMO_PASSWORD),
                nickname=u["nickname"],
                is_admin=u["is_admin"],
                is_buyer=True,
                is_seller=True,
                credit_score=u["credit"],
                risk_tag=u["risk_tag"],
                status=u.get("status", "active"),
                avatar_seed=u["avatar_seed"],
                is_ai=u.get("is_ai", False),
                ai_persona=u.get("ai_persona", ""),
                created_at=_naive(datetime.now(timezone.utc) - timedelta(days=30)),
            )
            session.add(user)
            user_map[u["student_no"]] = user
        session.flush()

        # ---------------- 商品 ----------------
        now = _naive(datetime.now(timezone.utc))
        for idx, (seller_no, title, cat, cond, price, pmin, pmax, status, image, desc) in enumerate(ITEMS, start=1):
            rejected = status == "rejected"
            frozen = status == "frozen"
            reasons = [{"rule": "auto_pass", "detail": "商品描述完整、图片清晰且未命中违禁词，规则引擎自动审核通过。"}]
            if rejected:
                reasons = [{"rule": "reject", "detail": "商品描述过短且成色较差（五成新、底座掉漆），建议补充实物细节图后重新提交。"}]
            elif frozen:
                reasons = [
                    {"rule": "banned_word", "detail": "命中校园禁售/危险物品词：『大功率』，宿舍禁用 3000W 电热器件，触发安全否决。"},
                    {"rule": "banned_word", "detail": "命中校园禁售/危险物品词：『热得快』，存在用电安全隐患。"},
                ]
            item = Item(
                seller_id=user_map[seller_no].id,
                title=title,
                category=cat,
                condition_level=cond,
                attrs={"channel": "校园闲置直发", "inspection": "实物拍照核验"},
                description=desc,
                image_url=image,
                price_suggest_min=pmin,
                price_suggest_max=pmax,
                price=price,
                status=status,
                lock_version=1 if status in ("locked", "dealed") else 0,
                reject_count=1 if rejected else 0,
                audit_reason=reasons,
                created_at=now - timedelta(days=max(1, idx % 12)),
            )
            session.add(item)
        session.commit()

        # ---------------- Agent 注册记录 ----------------
        for a in AGENTS:
            session.add(AgentStatus(
                name=a["name"], display_name=a["display_name"], avatar=a["avatar"],
                accent=a["accent"], capabilities=a["capabilities"], description=a["description"],
                runtime_status="running", llm_mode="rule", msg_handled=0, tasks_handled=0,
                updated_at=now,
            ))
        session.commit()

    if light:
        return True
    seed_history()
    return True


# ---------------------------------------------------------------------------
# 历史订单 / 议价 / 评价 / 审计
# ---------------------------------------------------------------------------

def seed_history() -> None:
    with Session(engine) as session:
        items = {i.id: i for i in session.exec(select(Item)).all()}
        uid = {u.student_no: u.id for u in session.exec(select(User)).all()}
        users = {u.id: u for u in session.exec(select(User)).all()}

        def _review_delta(score: int) -> int:
            if score >= 4:
                return settings.credit_good_review
            if score == 3:
                return settings.credit_mid_review
            return settings.credit_bad_review

        def _apply_credit_change(target_id: int, delta: int, reason: str, when: datetime) -> None:
            u = users[target_id]
            u.credit_score = max(0, u.credit_score + delta)
            session.add(AuditLogSafe(
                session, "agent", "credit", "credit_change", "user", target_id,
                {"delta": delta, "reason": reason, "new_score": u.credit_score}, when,
            ))

        for seq, (buyer_no, seller_no, item_idx, deal_price, status, br, sr, days) in enumerate(HISTORY_ORDERS, start=1):
            item = items[item_idx]
            buyer_id, seller_id = uid[buyer_no], uid[seller_no]
            t0 = _naive(datetime.now(timezone.utc) - timedelta(days=days, hours=4))
            buyer_reserve = round(deal_price * 1.08, 1)
            seller_reserve = round(deal_price * 0.92, 1)
            nash = round((buyer_reserve + seller_reserve) / 2, 1)
            first_offer = round(deal_price * 0.88, 1)

            neg = Negotiation(
                item_id=item.id, buyer_id=buyer_id, seller_id=seller_id,
                buyer_reserve=buyer_reserve, seller_reserve=seller_reserve,
                nash_price=nash, max_rounds=5, deadline_seconds=120,
                status="deal", deal_price=deal_price,
                created_at=t0, closed_at=t0 + timedelta(minutes=6),
            )
            session.add(neg)
            session.flush()
            offers = [
                (first_offer, "buyer", f"第 1 轮买方出价，参考纳什价 ¥{nash:g}"),
                (round(deal_price * 1.04, 1), "seller", "第 1 轮卖方要价，接近双方交集"),
                (deal_price, "buyer", f"接受成交价 ¥{deal_price:g}"),
            ]
            for rnd, (price, role, basis) in enumerate(offers, start=1):
                session.add(Offer(
                    negotiation_id=neg.id, round=rnd, from_role=role, price=price,
                    basis=basis, created_at=t0 + timedelta(minutes=rnd * 2),
                ))

            pay_deadline = t0 + timedelta(minutes=15)
            order = Order(
                order_no=f"ORD2026{seq:04d}{item.id:02d}",
                item_id=item.id, negotiation_id=neg.id, buyer_id=buyer_id, seller_id=seller_id,
                deal_price=deal_price, status=status, lock_token=None,
                pay_deadline=None if status in ("canceled",) else pay_deadline,
                created_at=t0 + timedelta(minutes=6), updated_at=t0 + timedelta(hours=2),
            )
            session.add(order)
            session.flush()

            # 审计轨迹
            session.add(AuditLogSafe(session, actor_type="agent", actor_id="coordinator",
                                    action="flow_start", target_type="order", target_id=order.id,
                                    detail={"flow": "trade", "business": {"order_id": order.id}},
                                    created=t0 + timedelta(minutes=6)))
            session.add(AuditLogSafe(session, actor_type="agent", actor_id="order",
                                    action="order_created", target_type="order", target_id=order.id,
                                    detail={"deal_price": deal_price}, created=t0 + timedelta(minutes=6)))

            if status in ("paid", "receiving", "completed", "reviewed", "refunded", "appealing"):
                paid_at = t0 + timedelta(hours=1)
                session.add(AuditLogSafe(session, "user", buyer_id, "pay", "order", order.id,
                                        {"deal_price": deal_price}, paid_at))
            if status in ("receiving", "completed", "reviewed", "refunded", "appealing"):
                session.add(AuditLogSafe(session, "user", seller_id, "order_receiving", "order", order.id,
                                        {"from": "paid"}, t0 + timedelta(hours=2)))
            if status in ("completed", "reviewed", "refunded"):
                session.add(AuditLogSafe(session, "user", buyer_id, "order_completed", "order", order.id,
                                        {"from": "receiving"}, t0 + timedelta(hours=3)))
            if status == "canceled":
                session.add(AuditLogSafe(session, "agent", "order", "order_canceled", "order", order.id,
                                        {"reason": "买家未在 15 分钟内支付，系统自动取消并释放锁"},
                                        t0 + timedelta(hours=20)))
            if status == "refunded":
                session.add(AuditLogSafe(session, "admin", "coordinator", "ruling_applied", "order", order.id,
                                        {"ruling": "refund", "basis": "货不对板且金额 ≤ 直裁阈值，规则裁决退款并扣卖家信用。"},
                                        t0 + timedelta(days=1)))
                session.add(Appeal(
                    order_id=order.id, appellant_id=buyer_id, reason="收到的充电宝外壳有裂痕，与描述不符，要求退款。",
                    status="ruled", ruling="refund", ruling_basis="货不对板证据成立，小额规则直裁退款。",
                    judged_by="coordinator",
                    created_at=t0 + timedelta(hours=6), ruled_at=t0 + timedelta(days=1),
                ))
                _apply_credit_change(seller_id, -4,
                                     f"订单 {order.order_no} 货不对板退款裁决，卖家履约责任扣分",
                                     t0 + timedelta(days=1))

            # 评价
            if br is not None:
                session.add(Review(order_id=order.id, from_user_id=buyer_id, to_user_id=seller_id,
                                  score=br, content="交易顺利，商品与描述一致，学长很耐心！",
                                  created_at=t0 + timedelta(hours=5)))
                session.add(AuditLogSafe(session, "user", buyer_id, "review", "user", seller_id,
                                        {"order_id": order.id, "delta": _review_delta(br)}, t0 + timedelta(hours=5)))
                _apply_credit_change(seller_id, _review_delta(br),
                                     f"订单 {order.order_no} 收到买家 {br} 星评价",
                                     t0 + timedelta(hours=5))
            if sr is not None:
                session.add(Review(order_id=order.id, from_user_id=seller_id, to_user_id=buyer_id,
                                  score=sr, content="买家付款爽快，沟通愉快，欢迎再次交易。",
                                  created_at=t0 + timedelta(hours=5, minutes=10)))
                session.add(AuditLogSafe(session, "user", seller_id, "review", "user", buyer_id,
                                        {"order_id": order.id, "delta": _review_delta(sr)}, t0 + timedelta(hours=5, minutes=10)))
                _apply_credit_change(buyer_id, _review_delta(sr),
                                     f"订单 {order.order_no} 收到卖家 {sr} 星评价",
                                     t0 + timedelta(hours=5, minutes=10))

        # ------------------------------------------------------------------
        # 追加历史实例块（不动既有 HISTORY_ORDERS 顺序与编号）：
        # A. 冻结账号 20240008 作为买家买入李学姐耳机：已支付未收到货/卖家失联，
        #    挂一条 pending 申诉（管理员纠纷终裁台与「我的申诉」真实待办）；
        # B. 冻结账号另一笔超时未付取消订单，并留信用扣分轨迹；
        # C. 赵一鸣 20240004 买入张学长 Apple Pencil：议价含「用户代理授权区间
        #    自动出价（越界已二次确认）」出价轨迹，已成交并互评。
        # ------------------------------------------------------------------
        def _extra_history_order(*, seq: int, item_idx: int, buyer_no: str, seller_no: str,
                                 deal_price: float, status: str, days: int,
                                 offer_rows: list[tuple], br: int | None = None,
                                 sr: int | None = None) -> tuple[Order, datetime]:
            item = items[item_idx]
            buyer_id, seller_id = uid[buyer_no], uid[seller_no]
            t0 = _naive(datetime.now(timezone.utc) - timedelta(days=days, hours=4))
            buyer_reserve = round(deal_price * 1.08, 1)
            seller_reserve = round(deal_price * 0.92, 1)
            nash = round((buyer_reserve + seller_reserve) / 2, 1)

            neg = Negotiation(
                item_id=item.id, buyer_id=buyer_id, seller_id=seller_id,
                buyer_reserve=buyer_reserve, seller_reserve=seller_reserve,
                nash_price=nash, max_rounds=5, deadline_seconds=120,
                status="deal", deal_price=deal_price,
                created_at=t0, closed_at=t0 + timedelta(minutes=2 * len(offer_rows) + 2),
            )
            session.add(neg)
            session.flush()
            for rnd, (price, role, basis) in enumerate(offer_rows, start=1):
                session.add(Offer(
                    negotiation_id=neg.id, round=rnd, from_role=role, price=price,
                    basis=basis, created_at=t0 + timedelta(minutes=rnd * 2),
                ))

            close_minutes = 2 * len(offer_rows)
            order = Order(
                order_no=f"ORD2026{seq:04d}{item.id:02d}",
                item_id=item.id, negotiation_id=neg.id, buyer_id=buyer_id, seller_id=seller_id,
                deal_price=deal_price, status=status, lock_token=None,
                pay_deadline=None if status == "canceled" else t0 + timedelta(minutes=15),
                created_at=t0 + timedelta(minutes=close_minutes),
                updated_at=t0 + timedelta(hours=2),
            )
            session.add(order)
            session.flush()
            session.add(AuditLogSafe(session, actor_type="agent", actor_id="coordinator",
                                    action="flow_start", target_type="order", target_id=order.id,
                                    detail={"flow": "trade", "business": {"order_id": order.id}},
                                    created=t0 + timedelta(minutes=close_minutes)))
            session.add(AuditLogSafe(session, actor_type="agent", actor_id="order",
                                    action="order_created", target_type="order", target_id=order.id,
                                    detail={"deal_price": deal_price},
                                    created=t0 + timedelta(minutes=close_minutes)))
            if status in ("paid", "receiving", "completed", "reviewed", "refunded", "appealing"):
                session.add(AuditLogSafe(session, "user", buyer_id, "pay", "order", order.id,
                                        {"deal_price": deal_price}, t0 + timedelta(hours=1)))
            if status in ("receiving", "completed", "reviewed", "refunded", "appealing"):
                session.add(AuditLogSafe(session, "user", seller_id, "order_receiving", "order", order.id,
                                        {"from": "paid"}, t0 + timedelta(hours=2)))
            if status in ("completed", "reviewed", "refunded"):
                session.add(AuditLogSafe(session, "user", buyer_id, "order_completed", "order", order.id,
                                        {"from": "receiving"}, t0 + timedelta(hours=3)))
            if status == "canceled":
                session.add(AuditLogSafe(session, "agent", "order", "order_canceled", "order", order.id,
                                        {"reason": "买家未在 15 分钟内支付，系统自动取消并释放锁"},
                                        t0 + timedelta(hours=20)))
            if br is not None:
                session.add(Review(order_id=order.id, from_user_id=buyer_id, to_user_id=seller_id,
                                  score=br, content="交易顺利，商品与描述一致，学长很耐心！",
                                  created_at=t0 + timedelta(hours=5)))
                session.add(AuditLogSafe(session, "user", buyer_id, "review", "user", seller_id,
                                        {"order_id": order.id, "delta": _review_delta(br)},
                                        t0 + timedelta(hours=5)))
                _apply_credit_change(seller_id, _review_delta(br),
                                     f"订单 {order.order_no} 收到买家 {br} 星评价",
                                     t0 + timedelta(hours=5))
            if sr is not None:
                session.add(Review(order_id=order.id, from_user_id=seller_id, to_user_id=buyer_id,
                                  score=sr, content="买家付款爽快，沟通愉快，欢迎再次交易。",
                                  created_at=t0 + timedelta(hours=5, minutes=10)))
                session.add(AuditLogSafe(session, "user", seller_id, "review", "user", buyer_id,
                                        {"order_id": order.id, "delta": _review_delta(sr)},
                                        t0 + timedelta(hours=5, minutes=10)))
                _apply_credit_change(buyer_id, _review_delta(sr),
                                     f"订单 {order.order_no} 收到卖家 {sr} 星评价",
                                     t0 + timedelta(hours=5, minutes=10))
            return order, t0

        frozen_id = uid["20240008"]

        # A. 已付款未收到货 + 卖家失联 → pending 申诉（订单保持 paid，尚未进入申诉流）
        order_paid, t_paid = _extra_history_order(
            seq=10, item_idx=35, buyer_no="20240008", seller_no="20240002",
            deal_price=65.0, status="paid", days=2,
            offer_rows=[
                (58.0, "buyer", "第 1 轮买方出价，参考纳什价与九成新定价"),
                (70.0, "seller", "第 1 轮卖方要价，耳机成色好附件齐全"),
                (65.0, "buyer", "接受成交价 ¥65，约图书馆门口当天面交"),
            ],
        )
        session.add(Appeal(
            order_id=order_paid.id, appellant_id=frozen_id,
            reason="付款已经两天，卖家一直没有确认发货，约好的面交地点也没有出现；"
                   "站内消息多次已读不回、电话无人接听，疑似卖家失联。我至今未收到货，"
                   "请求平台介入核实并协助退款。",
            evidence={}, status="pending",
            created_at=t_paid + timedelta(hours=26),
        ))

        # B. 超时未付取消 → 信用扣分轨迹（冻结账号信用轨迹）
        order_canceled, t_canceled = _extra_history_order(
            seq=11, item_idx=36, buyer_no="20240008", seller_no="20240002",
            deal_price=14.0, status="canceled", days=9,
            offer_rows=[
                (12.0, "buyer", "第 1 轮买方出价，希望凑单便宜些"),
                (16.0, "seller", "第 1 轮卖方要价，书很新不议价空间有限"),
                (14.0, "buyer", "接受成交价 ¥14，但之后一直未完成支付"),
            ],
        )
        _apply_credit_change(
            frozen_id, settings.credit_pay_timeout,
            f"订单 {order_canceled.order_no} 拍下后超时未支付且多次催办无回应，"
            f"按规则扣除信用 {abs(settings.credit_pay_timeout)} 分",
            t_canceled + timedelta(hours=20),
        )

        # C. 用户代理授权区间自动出价（越界已二次确认）→ 成交互评
        _extra_history_order(
            seq=12, item_idx=37, buyer_no="20240004", seller_no="20240001",
            deal_price=400.0, status="reviewed", days=7, br=5, sr=5,
            offer_rows=[
                (360.0, "buyer", "第 1 轮买方手动出价，参考建议价区间下限"),
                (440.0, "seller", "第 1 轮卖方要价，配件齐全且笔身无划痕"),
                (380.0, "agent",
                 "用户代理授权区间自动出价（越界已二次确认）：在授权区间 ¥360–390 内"
                 "代客出价 ¥380；卖方要价 ¥440 超出授权上限，已向用户弹窗二次确认，"
                 "用户明确追加授权上限至 ¥400 后继续议价。"),
                (400.0, "seller", "卖方让至 ¥400，请求买方确认成交"),
                (400.0, "buyer",
                 "用户代理回传成交前确认：用户同意按 ¥400 成交，代为接受，议价达成。"),
            ],
        )

        # ------------------------------------------------------------------
        # D. V5 T4（AC-7）：管理员 2400320321 买/卖历史与 AI 摊主历史成交
        #   D1 管理员买入张学长 iPad Air4：3 轮议价、已互评双 5 星（+2 信用轨迹）
        #   D2 管理员买入李学姐降噪耳机：已支付待收货
        #   D3 管理员买入 AI 校园摊主台灯：拍下待支付（议价步骤时间线完整）
        #   D4 管理员作为卖家卖给钱多多机械键盘：已完成
        #   D5 赵一鸣与 AI 校园摊主成交真无线耳机：已互评（与 AI 也能成交）
        # ------------------------------------------------------------------

        # D1 管理员买家 · reviewed · 双 5 星
        _extra_history_order(
            seq=13, item_idx=56, buyer_no="2400320321", seller_no="20240001",
            deal_price=1980.0, status="reviewed", days=8, br=5, sr=5,
            offer_rows=[
                (1880.0, "buyer", "第 1 轮买方出价，参考二手平板行情与电池健康估价"),
                (2080.0, "seller", "第 1 轮卖方要价，配件齐全且无拆修，已接近建议价下限"),
                (1980.0, "buyer", "接受成交价 ¥1980，约图书馆当面验机后完成交易"),
            ],
        )

        # D2 管理员买家 · receiving 待收货
        _extra_history_order(
            seq=14, item_idx=57, buyer_no="2400320321", seller_no="20240002",
            deal_price=175.0, status="receiving", days=1,
            offer_rows=[
                (160.0, "buyer", "第 1 轮买方出价，希望按二手行情小刀一下"),
                (185.0, "seller", "第 1 轮卖方要价，耳机成色新且降噪功能正常"),
                (175.0, "buyer", "接受成交价 ¥175，已付款，约晚饭时间食堂门口面交"),
            ],
        )

        # D3 管理员买家 · unpaid 待支付（含完整议价步骤时间线）
        _extra_history_order(
            seq=15, item_idx=58, buyer_no="2400320321", seller_no="AI10001",
            deal_price=78.0, status="unpaid", days=0,
            offer_rows=[
                (70.0, "buyer", "第 1 轮买方出价，凑单希望再便宜一些"),
                (85.0, "seller", "第 1 轮 AI 摊主要价，台灯几乎全新、功能完好"),
                (78.0, "buyer", "接受成交价 ¥78，订单已生成，等待买家支付"),
            ],
        )

        # D4 管理员卖家 · completed 已完成（买家钱多多）
        _extra_history_order(
            seq=16, item_idx=54, buyer_no="20240005", seller_no="2400320321",
            deal_price=66.0, status="completed", days=3, sr=4,
            offer_rows=[
                (60.0, "buyer", "第 1 轮买方出价，学生党预算有限"),
                (72.0, "seller", "第 1 轮卖方要价，茶轴手感好且附赠皮质手托"),
                (66.0, "buyer", "接受成交价 ¥66，约教学楼大厅当面交易"),
            ],
        )

        # D5 AI 校园摊主卖家 · reviewed（买家赵一鸣，体现与 AI 也能成交）
        _extra_history_order(
            seq=17, item_idx=59, buyer_no="20240004", seller_no="AI10001",
            deal_price=95.0, status="reviewed", days=5, br=5, sr=5,
            offer_rows=[
                (85.0, "buyer", "第 1 轮买方出价，参考同款耳机二手行情"),
                (105.0, "seller", "第 1 轮 AI 摊主要价，耳机在保且配件齐全"),
                (95.0, "buyer", "接受成交价 ¥95，AI 摊主回复爽快，面交顺利"),
            ],
        )

        session.commit()


def AuditLogSafe(session, actor_type, actor_id, action, target_type, target_id, detail, created):
    """构造 AuditLog（直接 add，由外层统一 commit）。"""
    from app.models import AuditLog

    return AuditLog(
        actor_type=actor_type, actor_id=str(actor_id), action=action,
        target_type=target_type, target_id=str(target_id), detail=detail,
        created_at=created,
    )


# ---------------------------------------------------------------------------
# 真实演示流程（控制台编排追踪/黑板/冲突中心数据）
# 在 lifespan 中事件循环绑定后调用；临时切 RuleLLM 保证确定性，结束后恢复。
# ---------------------------------------------------------------------------

def seed_demo_flows() -> dict:
    """运行真实 LangGraph 流程，返回各等待实例 thread_id（供测试/调试引用）。"""
    # 幂等引导（lifespan 已执行时无副作用；独立脚本场景下完成图/Agent 注册）
    from app.agents.bootstrap import bootstrap_agents
    from app.graph.checkpoint import init_checkpointer
    from app.graph.flows import bootstrap_flows
    from app.graph.runner import runner
    from app.llm import client as llm_mod

    init_checkpointer()
    bootstrap_flows()
    bootstrap_agents()

    refs: dict[str, str] = {}
    original_client = llm_mod.llm_client._client
    llm_mod.llm_client._client = None  # 演示播种使用确定性规则
    try:
        with Session(engine) as session:
            users = {u.student_no: u for u in session.exec(select(User)).all()}
            items = {i.id: i for i in session.exec(select(Item)).all()}
            seller1 = users["20240001"].id
            seller2 = users["20240002"].id
            seller3 = users["20240003"].id
            buyer5 = users["20240005"].id
            buyer6 = users["20240006"].id
            buyer7 = users["20240007"].id
            # 提前固化后续要用到的商品主键为整型，
            # 避免会话 rollback/commit/expunge 后 ORM 对象过期失联
            item16, item14, item19, item13, item10 = (
                int(items[16].id), int(items[14].id), int(items[19].id),
                int(items[13].id), int(items[10].id),
            )

            # F1 安全否决等待（veto_gate）
            r1 = runner.start("publish", user_id=seller3,
                              title="热得快电热棒", description="出热得快电热棒，宿舍烧水大功率3000W神器，30元", price=30.0)
            refs["veto_waiting"] = r1["thread_id"]

            # F2 存疑转人工等待（human_review_gate）
            r2 = runner.start("publish", user_id=seller1,
                              title="高仿运动鞋", description="全新高仿精仿一比一运动鞋，质量很好，懂的来，120元出", price=120.0)
            refs["manual_waiting"] = r2["thread_id"]

            # 发布流只做自然语言建档、不产图，为两个演示商品补真实图片（避免前端破图）
            # 注意：本会话在开头查询 users/items 时已开启事务快照，需先 rollback
            # 才能看到发布 Agent 在独立会话中新提交的商品行；
            # 同时把后续要用的主键固化为整型，避免 commit 过期 + expunge 导致 DetachedInstance
            session.rollback()
            no_image = or_(Item.image_url.is_(None), Item.image_url == "")
            for _kw, _img_name in (("热得快", "item-rod"), ("高仿运动鞋", "item-shoes")):
                for _it in session.exec(
                    select(Item).where(Item.title.like(f"%{_kw}%"), no_image)
                ).all():
                    _it.image_url = _img(_img_name)
            session.commit()

            # F3 + C2：两买家在计算器(16, 卖家3)在售时先后发起议价，卖家依次接受
            # 先成交者加锁，后成交者在成交瞬间触发 C2 资源冲突
            from app.kernel.dispatch import call_agent as _call
            # FR-2 用户代理：自然语言意图 → 结构化（保留价/画像），仅产生 ACL 协作轨迹
            _call("user_agent", f"seed-intent-{buyer5}-{time.time_ns()}",
                  {"action": "parse_intent", "user_id": buyer5,
                   "text": "想收一台卡西欧计算器，预算 60 元以内"},
                  summary="用户代理解析买家自然语言意图与保留价")
            _call("user_agent", f"seed-intent-{buyer7}-{time.time_ns()}",
                  {"action": "parse_intent", "user_id": buyer7,
                   "text": "这个佳能相机 260 元我要了，帮我议价下单"},
                  summary="高风险买家意图结构化，供信用风险画像参考")
            nid_b5 = _start_neg(buyer5, item16, reserve=60, first=48)
            nid_b4 = _start_neg(users["20240004"].id, item16, reserve=60, first=47)
            deal3 = _accept_neg(session, nid_b5, price=48, seller_id=seller3)
            refs["pay_waiting"] = deal3
            _accept_neg(session, nid_b4, price=47, seller_id=seller3)

            # F4 灰区风险（信用75买家）→ 风险终裁等待（risk_human_gate）：佳能相机(14, 卖家2)
            deal4 = _drive_deal(session, buyer7, item14, reserve=300, first=260,
                                seller_id_for_accept=seller2)
            refs["risk_waiting"] = deal4

            # F5 大额交易支付后申诉 → 纠纷终裁等待（appeal_human_gate，吉他 420 > 50）
            deal5 = _drive_deal(session, buyer5, item19, reserve=450, first=380,
                                seller_id_for_accept=seller3)
            oid5 = _oid(session, deal5)
            _pay_order(session, deal5, buyer5)
            appeal_row = Appeal(
                order_id=oid5, appellant_id=buyer5,
                reason="吉他琴颈有明显弯曲，打品严重，与描述的『音准稳定』不符，申请退货退款。",
                status="pending",
                created_at=_naive(datetime.now(timezone.utc)),
            )
            session.add(appeal_row)
            session.commit()
            session.refresh(appeal_row)
            appeal5 = runner.start("appeal", user_id=buyer5, appeal_id=appeal_row.id, order_id=oid5)
            refs["appeal_waiting"] = appeal5["thread_id"]

            # C6 历史：高风险 68 分买家成交 Kindle(13, 卖家2) → 加权投票拦截
            _drive_deal(session, buyer6, item13, reserve=340, first=280,
                        seller_id_for_accept=seller2)

            # C1 历史：无交集 5 轮议价 → 破裂（物理真题 10，真实卖家 3）
            c1_nid = _drive_stalemate(session, buyer5, seller3, item10)
            # FR-2 用户代理：破裂会话上的代客出价演示（区间内建议 + 成交前必须确认）
            _call("user_agent", f"seed-autobid-{c1_nid}",
                  {"action": "auto_bid", "negotiation_id": c1_nid, "authorized_max": 30},
                  summary="用户代理在授权区间内给出代客出价建议")
            _call("user_agent", f"seed-autobid-confirm-{c1_nid}",
                  {"action": "auto_bid", "negotiation_id": c1_nid, "authorized_max": 200},
                  summary="接受卖家要价将立即成交，成交前请求用户二次确认")
    finally:
        llm_mod.llm_client._client = original_client  # 恢复真实 LLM 客户端
    return refs


def _oid(session, thread_id: str) -> int | None:
    from app.graph.runner import runner

    snap = runner.get_state(thread_id)
    return snap["state"].get("order_id")


def _start_neg(buyer_id: int, item_id: int, reserve: float, first: float) -> int:
    """买家发起议价（商品必须在售），返回 negotiation_id。"""
    from app.kernel.dispatch import call_agent

    s = call_agent("negotiation", f"seed-start-{buyer_id}-{item_id}-{time.time_ns()}",
                   {"action": "start_negotiation", "buyer_id": buyer_id, "item_id": item_id,
                    "buyer_reserve": reserve, "first_offer": first},
                   summary="演示数据：发起议价", thread_id=None)
    return s.payload["negotiation_id"]


def _accept_neg(session, nid: int, price: float, seller_id: int) -> str:
    """卖家接受价格成交，返回 trade flow thread_id（锁冲突时返回空串）。"""
    from sqlmodel import select as _sel

    from app.kernel.dispatch import call_agent
    from app.models import Order as _O

    call_agent("negotiation", f"seed-offer-{nid}-{time.time_ns()}",
               {"action": "offer", "negotiation_id": nid, "user_id": seller_id,
                "price": price, "confirm": True},
               summary="演示数据：卖家接受出价成交", thread_id=None)
    order = session.exec(_sel(_O).where(_O.negotiation_id == nid)).first()
    session.expunge_all()
    return order.graph_thread_id if order else ""


def _drive_deal(session, buyer_id: int, item_id: int, reserve: float, first: float,
                seller_id_for_accept: int) -> str:
    """发起并立即接受成交，返回 trade thread_id。"""
    nid = _start_neg(buyer_id, item_id, reserve=reserve, first=first)
    return _accept_neg(session, nid, price=first, seller_id=seller_id_for_accept)


def _drive_stalemate(session, buyer_id: int, seller_id: int, item_id: int) -> int:
    from app.kernel.dispatch import call_agent

    s = call_agent("negotiation", f"seed-c1-start-{item_id}-{time.time_ns()}",
                   {"action": "start_negotiation", "buyer_id": buyer_id, "item_id": item_id,
                    "buyer_reserve": 10, "first_offer": 5},
                   summary="C1 演示：低保留价议价", thread_id=None)
    nid = s.payload["negotiation_id"]
    seller_prices = [100, 90, 80, 70, 60]
    buyer_prices = [7, 8, 9, 10]
    call_agent("negotiation", f"seed-c1-{nid}",
               {"action": "offer", "negotiation_id": nid, "user_id": seller_id,
                "price": seller_prices[0], "confirm": True},
               summary="C1 演示：卖家首轮不让步", thread_id=None)
    for i in range(4):
        call_agent("negotiation", f"seed-c1-{nid}",
                   {"action": "offer", "negotiation_id": nid, "user_id": buyer_id,
                    "price": buyer_prices[i]}, summary="C1 演示：买方小步让步", thread_id=None)
        call_agent("negotiation", f"seed-c1-{nid}",
                   {"action": "offer", "negotiation_id": nid, "user_id": seller_id,
                    "price": seller_prices[i + 1], "confirm": True},
                   summary="C1 演示：卖方坚持高价", thread_id=None)
    return nid


def _pay_order(session, thread_id: str, buyer_id: int) -> None:
    """对等待支付门的流程执行 resume 支付。"""
    from app.graph.runner import runner

    runner.resume(thread_id, {"action": "pay", "admin_id": "", "basis": "", "user_id": buyer_id})

"""全局配置：所有阈值集中于此，可被 .env 覆盖。"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---------- 基础 ----------
    app_name: str = "Campus Second-hand MAS"
    debug: bool = True
    database_url: str = "sqlite:///./campus_mas.db"

    # ---------- 认证 ----------
    jwt_secret: str = "campus-mas-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    # ---------- LLM ----------
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: int = 20
    llm_max_retry: int = 1

    # ---------- 议价 ----------
    neg_max_rounds: int = 5
    neg_deadline_seconds: int = 120
    # 一级对等协商最大轮次（区别于议价会话；spec 8.2：≤3 轮）
    consult_max_rounds: int = 3

    # ---------- 熔断代管 ----------
    breaker_fail_limit: int = 3

    # ---------- 订单 ----------
    pay_timeout_minutes: int = 15

    # ---------- 信用规则 ----------
    credit_initial: int = 100
    credit_good_review: int = 2
    credit_mid_review: int = 0
    credit_bad_review: int = -5
    credit_fault_penalty: int = -15
    credit_pay_timeout: int = -2
    high_risk_threshold: int = 80
    risk_confidence_threshold: float = 0.6

    # ---------- 投票（信用/审核/协调者三方，票权×置信度）----------
    vote_weight_credit: float = 0.5
    vote_weight_moderation: float = 0.2
    vote_weight_coordinator: float = 0.3
    vote_pass_score: float = 0.5
    vote_block_score: float = -0.5

    # ---------- 全局效用函数 U（spec 6.3 / 8.3，权重配置化）----------
    util_w_satisfaction: float = 0.25
    util_w_success: float = 0.20
    util_w_safety: float = 0.30
    util_w_fairness: float = 0.15
    util_w_cost: float = 0.10
    # C5 目标相容性：推荐方案满意度低于该阈值即要求重排
    util_reorder_min_satisfaction: float = 0.8

    # ---------- 申诉 ----------
    direct_ruling_max_amount: float = 50.0

    # ---------- 演示数据 ----------
    # 1=首次启动播种历史订单与真实演示流程（控制台示例）；0=仅基础账号/商品（测试用）
    seed_demo: bool = os.getenv("SEED_DEMO_DATA", "1") != "0"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.deepseek_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

$dir = "e:\project\大三上\Second-Hand-Trading-Muiti-Agent\frontend\public\images\items"
$items = @(
  @("item-skincare", "E-commerce product photo for campus second-hand marketplace: minimalist skincare gift set with cleanser toner lotion bottles on clean white desk, soft daylight, realistic studio product photography"),
  @("item-snacks", "E-commerce product photo for campus second-hand marketplace: assorted Asian snack gift box bundle with colorful packaged snacks, dorm desk, bright clean background, realistic product photo"),
  @("item-chair", "E-commerce product photo for campus second-hand marketplace: ergonomic grey mesh office desk chair with lumbar support, clean light background dorm room, realistic product photography"),
  @("item-ukulele", "E-commerce product photo for campus second-hand marketplace: natural wood soprano ukulele small guitar leaning on white wall, warm soft light, realistic product photo"),
  @("item-monitor", "E-commerce product photo for campus second-hand marketplace: 24 inch slim IPS computer monitor displaying soft gradient screen on clean student desk, realistic product photography"),
  @("item-backpack", "E-commerce product photo for campus second-hand marketplace: dark blue casual campus backpack school bag with laptop compartment, light grey seamless background, realistic product photo"),
  @("item-watercup", "E-commerce product photo for campus second-hand marketplace: stainless steel insulated thermos water bottle matte white with tea infuser, clean bright background, realistic product photo"),
  @("item-laptop", "E-commerce product photo for campus second-hand marketplace: silver lightweight student laptop open on wooden study desk with notebook and pen, soft window light, realistic product photography"),
  @("item-earbuds2", "E-commerce product photo for campus second-hand marketplace: white true wireless bluetooth earbuds with open charging case, clean light grey background, soft shadow, realistic product photo"),
  @("item-skates", "E-commerce product photo for campus second-hand trading marketplace: black inline roller skates blades on outdoor basketball court ground at sunset, realistic product photography"),
  @("item-textbook2", "E-commerce product photo for campus second-hand marketplace: stack of Chinese graduate entrance exam politics and English review textbooks with highlighted notes, wooden desk, realistic product photo"),
  @("item-badminton", "E-commerce product photo for campus second-hand marketplace: two carbon badminton rackets with shuttlecock on gym floor, bright indoor sports hall background, realistic product photography")
)
$jobs = @()
foreach($it in $items){
  $name=$it[0]; $prompt=[uri]::EscapeDataString($it[1])
  $out=Join-Path $dir "$name.jpg"
  if(Test-Path $out){ if((Get-Item $out).Length -gt 20000){ Write-Output "SKIP $name"; continue } }
  $url="https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=$prompt&image_size=square_hd"
  $jobs += Start-Job -ArgumentList $url,$out,$name -ScriptBlock {
    param($u,$o,$n)
    try { Invoke-WebRequest -Uri $u -OutFile $o -UseBasicParsing -TimeoutSec 300; "OK $n $((Get-Item $o).Length)" }
    catch { "FAIL $n $($_.Exception.Message)" }
  }
  while((Get-Job -State Running).Count -ge 4){ Start-Sleep -Seconds 2 }
}
Wait-Job $jobs | Out-Null
foreach($j in $jobs){ Receive-Job $j }
Remove-Job $jobs
Write-Output "ALL DONE"

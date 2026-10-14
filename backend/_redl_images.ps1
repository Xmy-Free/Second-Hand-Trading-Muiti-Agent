$tmp = Join-Path $env:TEMP "v5imgs2"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
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
$placeholderLen = 176626
foreach($it in $items){
  $name=$it[0]; $prompt=[uri]::EscapeDataString($it[1])
  $url="https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=$prompt&image_size=square_hd"
  $out=Join-Path $tmp "$name.jpg"
  $ok=$false
  for($try=1; $try -le 8 -and -not $ok; $try++){
    try {
      Invoke-WebRequest -Uri "$url&t=$try$(Get-Random)" -OutFile $out -UseBasicParsing -TimeoutSec 300
      $len=(Get-Item $out).Length
      if($len -ne $placeholderLen){ $ok=$true; Write-Output "OK $name try=$try len=$len" }
      else { Write-Output "WAIT $name try=$try placeholder"; Start-Sleep -Seconds 12 }
    } catch { Write-Output "ERR $name $($_.Exception.Message)"; Start-Sleep -Seconds 8 }
  }
  if(-not $ok){ Write-Output "GIVEUP $name" }
}
Write-Output "RETRY DONE"

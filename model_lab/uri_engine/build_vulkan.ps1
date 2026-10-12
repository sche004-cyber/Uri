# Build llama.cpp (tag b11425 clone under D:\uri-model-lab\strata_research\llamacpp-b11425) with the Vulkan
# backend into D:\uri-model-lab\build\<name>. Research-only; the production runtime stays the release zip.
#   powershell -File model_lab\uri_engine\build_vulkan.ps1 -Name stock
#   powershell -File model_lab\uri_engine\build_vulkan.ps1 -Name rsseq -Source D:\uri-model-lab\strata_research\llamacpp-rsseq
param(
    [string]$Name = "stock",
    [string]$Source = "D:\uri-model-lab\strata_research\llamacpp-b11425",
    [string]$VulkanRoot = ""
)
$ErrorActionPreference = "Stop"
if (-not $VulkanRoot) {
    $cands = @("D:\uri-model-lab\VulkanSDK", "C:\VulkanSDK") | Where-Object { Test-Path $_ }
    foreach ($c in $cands) {
        $v = Get-ChildItem $c -Directory | Where-Object { Test-Path (Join-Path $_.FullName "Bin\glslc.exe") } | Sort-Object Name -Descending | Select-Object -First 1
        if ($v) { $VulkanRoot = $v.FullName; break }
        if (Test-Path (Join-Path $c "Bin\glslc.exe")) { $VulkanRoot = $c; break }
    }
}
# No-admin toolchain: Khronos headers + import lib generated from the system loader + the Android NDK's glslc.
$VkInc = "D:/uri-model-lab/vk/Vulkan-Headers/include"
$VkLib = "D:/uri-model-lab/vk/vulkan-1.lib"
$Glslc = "C:/Users/cheta/AppData/Local/Android/Sdk/ndk/28.2.13676358/shader-tools/windows-x86_64/glslc.exe"
if ($VulkanRoot) { $env:VULKAN_SDK = $VulkanRoot; $env:PATH = "$VulkanRoot\Bin;$env:PATH" }
$build = "D:\uri-model-lab\build\$Name"
New-Item -ItemType Directory -Force $build | Out-Null
$vcvars = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
$cmd = "call `"$vcvars`" && cmake -S `"$Source`" -B `"$build`" -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_VULKAN=ON -DVulkan_INCLUDE_DIR=`"$VkInc`" -DVulkan_LIBRARY=`"$VkLib`" -DVulkan_GLSLC_EXECUTABLE=`"$Glslc`" -DCMAKE_PREFIX_PATH=D:/uri-model-lab/vk/spirv-headers-install -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_TOOLS=ON -DGGML_NATIVE=OFF -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON && cmake --build `"$build`" --config Release --target llama-server llama-imatrix llama-bench -j 12"
Write-Host "Vulkan include=$VkInc lib=$VkLib glslc=$Glslc"
cmd /c $cmd
if ($LASTEXITCODE -ne 0) { throw "build failed rc=$LASTEXITCODE" }
Get-ChildItem "$build\bin" -Filter "llama-*.exe" | Select-Object Name, Length | Format-Table -AutoSize | Out-String

#!/usr/bin/env bash
#
# cloud_parse_response 的 PC 端单元测试
#
# 把真实的 network_client.c 与树里的 cJSON、mbedtls base64 一起编译后运行，
# 不打桩、不复制逻辑 —— 测的就是端侧将来真正跑的那份代码。
#
# 用法：
#   ./run.sh [openvela 工作区根目录]
#
# 工作区根目录指包含 apps/、nuttx/、external/ 的那一层。
# 不传参数时从本脚本位置向上自动查找。

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ---- 定位 openvela 工作区 ----
# 判据是"编译所需的目录都在"，而不只是 apps/ —— 部分同步的工作区
# 可能有 apps/ 却没有 external/curl，那样会误判。允许用 $1 显式指定。
is_workspace() {
    [ -d "$1/apps/include" ] && [ -d "$1/external/curl/curl/include" ]
}

WORKSPACE="${1:-}"
if [ -z "${WORKSPACE}" ]; then
    D="${SCRIPT_DIR}"
    while [ "${D}" != "/" ]; do
        if is_workspace "${D}"; then
            WORKSPACE="${D}"
            break
        fi
        D="$(dirname "${D}")"
    done
fi

if [ -z "${WORKSPACE}" ] || ! is_workspace "${WORKSPACE}"; then
    echo "错误：找不到可用的 openvela 工作区。" >&2
    echo "      需要同时具备 apps/include 与 external/curl/curl/include" >&2
    echo "      （sync 不完整的工作区会缺后者）。" >&2
    echo "用法：$0 <openvela 工作区根目录>" >&2
    exit 1
fi

echo "openvela 工作区: ${WORKSPACE}"

CJSON_DIR="${WORKSPACE}/apps/netutils/cjson/cJSON"
MBEDTLS_DIR="${WORKSPACE}/apps/crypto/mbedtls/mbedtls"

for d in "${CJSON_DIR}/cJSON.c" "${MBEDTLS_DIR}/library/base64.c" \
         "${MBEDTLS_DIR}/library/constant_time.c" \
         "${WORKSPACE}/external/curl/curl/include"; do
    if [ ! -e "${d}" ]; then
        echo "错误：缺少 ${d}" >&2
        exit 1
    fi
done

# ---- 编译 ----
# -ffunction-sections + --gc-sections：丢掉只被 cloud_send_audio / cloud_health_check
# 引用的 curl 符号，这样 PC 上无需链接 libcurl 也能测解析层。
OUT="$(mktemp -d)/cloud_parse_test"

gcc -g -O1 -o "${OUT}" \
    -I"${APP_DIR}" \
    -I"${WORKSPACE}/apps/include" \
    -I"${WORKSPACE}/external/curl/curl/include" \
    -I"${MBEDTLS_DIR}/include" \
    -I"${MBEDTLS_DIR}/library" \
    -ffunction-sections -Wl,--gc-sections \
    "${SCRIPT_DIR}/test_main.c" \
    "${APP_DIR}/network_client.c" \
    "${CJSON_DIR}/cJSON.c" \
    "${MBEDTLS_DIR}/library/base64.c" \
    "${MBEDTLS_DIR}/library/constant_time.c" \
    -lm

# ---- 运行 ----
echo
"${OUT}" "${SCRIPT_DIR}/fixtures"
RC=$?

rm -rf "$(dirname "${OUT}")"
exit ${RC}

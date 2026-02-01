const nextConfig = require("eslint-config-next/core-web-vitals")
const prettierConfig = require("eslint-config-prettier")

module.exports = [
  ...nextConfig,
  {
    rules: prettierConfig.rules
  }
]

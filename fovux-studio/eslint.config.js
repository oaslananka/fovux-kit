const tsParser = require("@typescript-eslint/parser");
const tsPlugin = require("@typescript-eslint/eslint-plugin");
const reactPlugin = require("eslint-plugin-react");

module.exports = [
  {
    ignores: ["out/**", "*.vsix", "node_modules/**"],
  },
  {
    files: ["src/**/*.{ts,tsx}", "test/**/*.ts"],
    plugins: {
      "@typescript-eslint": tsPlugin,
      react: reactPlugin,
    },
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        project: ["./tsconfig.json", "./tsconfig.eslint.json"],
        tsconfigRootDir: __dirname,
      },
    },
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_" },
      ],
      "react/prop-types": "off",
      "no-console": ["warn", { allow: ["warn", "error"] }],
    },
  },
];

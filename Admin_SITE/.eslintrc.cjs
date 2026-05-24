// Admin_SITE/.eslintrc.cjs
// V1.17.0j12: минимальный ESLint-конфиг, цель — поймать нарушения
// Rules of Hooks ДО билда (см. bug_class_hooks_after_early_return —
// «белый экран» после деплоя V1.17.0j9). Полный lint всего React
// не делаем сейчас: ставим только плагин react-hooks и его 2 правила.
// Скрипт: npm run lint (см. package.json).
module.exports = {
  root: true,
  env: { browser: true, es2022: true, node: true },
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
  },
  plugins: ['react-hooks'],
  rules: {
    'react-hooks/rules-of-hooks': 'error',
    'react-hooks/exhaustive-deps': 'warn',
  },
  ignorePatterns: ['dist', 'node_modules', '*.config.js'],
};

// logger.js

const RESET = '\x1b[0m';

const COLORS = {
  log: '\x1b[36m', // 青色
  info: '\x1b[34m', // 蓝色
  warn: '\x1b[33m', // 黄色
  error: '\x1b[31m' // 红色
};

const rawLog = console.log;
const rawInfo = console.info;
const rawWarn = console.warn;
const rawError = console.error;

console.log = (...args) => {
  rawLog(COLORS.log + args.join(' ') + RESET);
};

console.info = (...args) => {
  rawInfo(COLORS.info + args.join(' ') + RESET);
};

console.warn = (...args) => {
  rawWarn(COLORS.warn + args.join(' ') + RESET);
};

console.error = (...args) => {
  rawError(COLORS.error + args.join(' ') + RESET);
};

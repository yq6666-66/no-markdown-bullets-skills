/*
 * 去黑点 · 构建脚本
 *
 * 把引擎 qudiao.js 内联进页面模板 index.src.html，产出可独立发布的 index.html。
 * 目的：线上网关对每个请求都会校验 sharecode，外部 .js 子资源存在被拦截的风险；
 *       内联后整站零外部请求，单文件可直接打开、转发、离线使用。
 *
 * 用法：node build.js
 */
const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const TPL = path.join(ROOT, 'index.src.html');
const ENGINE = path.join(ROOT, 'qudiao.js');
const OUT = path.join(ROOT, 'index.html');

const tpl = fs.readFileSync(TPL, 'utf8');
const engine = fs.readFileSync(ENGINE, 'utf8');

// 安全护栏：引擎源码里若含 </script> 会提前闭合标签，必须拒绝构建
if (/<\/script/i.test(engine)) {
  console.error('构建失败：引擎源码包含 </script>，内联会破坏 HTML 结构');
  process.exit(1);
}

const TAG = '<script src="qudiao.js"></script>';
if (!tpl.includes(TAG)) {
  console.error('构建失败：模板中未找到占位标签 ' + TAG);
  process.exit(1);
}

const inline = '<script>\n/* === 清理引擎（由 build.js 从 qudiao.js 内联，请勿手改） === */\n'
  + engine.replace(/\s+$/, '')
  + '\n</script>';

const html = tpl.replace(TAG, inline);
fs.writeFileSync(OUT, html, 'utf8');

// 自检
const left = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>/g)].length;
const ext = [...html.matchAll(/<script[^>]*\bsrc=/g)].length;
console.log('构建完成');
console.log('  模板     :', path.basename(TPL), (tpl.length / 1024).toFixed(1) + ' KB');
console.log('  引擎     :', path.basename(ENGINE), (engine.length / 1024).toFixed(1) + ' KB');
console.log('  产物     :', path.basename(OUT), (html.length / 1024).toFixed(1) + ' KB');
console.log('  内联脚本 :', left, '个');
console.log('  外链脚本 :', ext, '个', ext === 0 ? '(单文件自包含)' : '(仍依赖外部文件)');

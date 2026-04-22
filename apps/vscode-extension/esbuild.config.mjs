import { build, context } from 'esbuild';

const isWatch = process.argv.includes('--watch');

/** @type {import('esbuild').BuildOptions} */
const extensionOptions = {
  entryPoints: ['src/extension.ts'],
  bundle: true,
  outdir: 'dist',
  platform: 'node',
  format: 'cjs',
  external: ['vscode'],
  sourcemap: true,
  minify: !isWatch,
  target: 'node18',
};

/** @type {import('esbuild').BuildOptions} */
const webviewOptions = {
  entryPoints: ['webview/main.js'],
  bundle: true,
  outfile: 'dist/webview.js',
  platform: 'browser',
  format: 'iife',
  sourcemap: true,
  minify: !isWatch,
  target: 'es2020',
};

if (isWatch) {
  const [extCtx, webCtx] = await Promise.all([
    context(extensionOptions),
    context(webviewOptions),
  ]);
  await Promise.all([extCtx.watch(), webCtx.watch()]);
  console.log('Watching for changes...');
} else {
  await Promise.all([build(extensionOptions), build(webviewOptions)]);
  console.log('Build complete.');
}

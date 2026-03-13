import { build, context } from 'esbuild';

const isWatch = process.argv.includes('--watch');

/** @type {import('esbuild').BuildOptions} */
const options = {
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

if (isWatch) {
  const ctx = await context(options);
  await ctx.watch();
  console.log('Watching for changes...');
} else {
  await build(options);
  console.log('Build complete.');
}

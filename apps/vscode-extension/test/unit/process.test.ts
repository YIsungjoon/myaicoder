import { describe, it, expect } from 'vitest';
import { buildServeArgs } from '../../src/mcp/process';

describe('buildServeArgs', () => {
  it('should return base args with defaults', () => {
    const args = buildServeArgs({});
    expect(args).toEqual(['serve']);
  });

  it('should include --allow-bash when enabled', () => {
    const args = buildServeArgs({ allowBash: true });
    expect(args).toContain('--allow-bash');
  });

  it('should include --max-concurrent when > 1', () => {
    const args = buildServeArgs({ maxConcurrent: 4 });
    expect(args).toContain('--max-concurrent');
    expect(args).toContain('4');
  });

  it('should not include --max-concurrent when 1', () => {
    const args = buildServeArgs({ maxConcurrent: 1 });
    expect(args).not.toContain('--max-concurrent');
  });

  it('should include --agentic when enabled', () => {
    const args = buildServeArgs({ enableAgentic: true });
    expect(args).toContain('--agentic');
  });

  it('should combine all flags', () => {
    const args = buildServeArgs({
      allowBash: true,
      maxConcurrent: 2,
      enableAgentic: true,
    });
    expect(args).toEqual(['serve', '--allow-bash', '--max-concurrent', '2', '--agentic']);
  });
});

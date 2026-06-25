export function mockDelay(ms = 450) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function withMockLoading<T>(work: () => T | Promise<T>, ms = 450) {
  await mockDelay(ms);
  return work();
}

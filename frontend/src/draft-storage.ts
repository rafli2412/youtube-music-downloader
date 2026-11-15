/** Keep autosave, explicit saves, and discard operations ordered across bridge requests. */
export class DraftWriteQueue {
  private tail: Promise<unknown> = Promise.resolve();

  enqueue<T>(operation: () => Promise<T>): Promise<T> {
    const task = this.tail.catch(() => undefined).then(operation);
    this.tail = task;
    return task;
  }
}

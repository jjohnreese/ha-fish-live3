// One source of truth for microphone state. Mute always wins over push-to-talk.
export function microphoneMuted({ mode, muted, held, active }) {
  return !active || muted || (mode === "ptt" && !held);
}

// An explicit Unmute action must actually open the microphone, including in PTT mode.
export function microphoneToggle(state) {
  return microphoneMuted(state)
    ? { mode: "handsfree", muted: false, held: false }
    : { muted: true, held: false };
}

export class MicController {
  constructor(apply) {
    this.apply = apply;
    this.state = {
      mode: "handsfree",
      muted: false,
      held: false,
      active: false,
    };
    this.queue = Promise.resolve();
    this.revision = 0;
  }
  update(patch) {
    Object.assign(this.state, patch);
    ++this.revision;
    this.queue = this.queue
      .catch(() => {})
      .then(async () => {
        const revision = this.revision;
        try {
          await this.apply(microphoneMuted(this.state));
        } catch (error) {
          if (this.revision === revision && this.state.active)
            Object.assign(this.state, { muted: true, held: false });
          throw error;
        }
      });
    return this.queue;
  }
}

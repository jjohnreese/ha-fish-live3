export function isEndRequest(text, wakePhrase = "") {
  const normalize = (value) =>
    String(value)
      .toLowerCase()
      .replace(/[’‘]/g, "'")
      .replace(/[.!?,;:]/g, " ")
      .replace(/\bcon-conversation\b/g, "conversation")
      .replace(/\s+/g, " ")
      .trim();
  let normalized = normalize(text),
    named = false,
    thanked = false;
  const name = normalize(wakePhrase),
    names = [name, name.replace(/^(?:hey|okay|ok) /, "")]
      .filter(Boolean)
      .sort((a, b) => b.length - a.length);
  for (let pass = 0; pass < 6; pass++) {
    const before = normalized;
    normalized = normalized
      .replace(/^(?:(?:ok(?:ay)?|hey|well|alright) +)+/, "")
      .replace(/ please$/, "")
      .replace(/(?<!for) now$/, "");
    for (const name of names) {
      if (normalized === name) {
        normalized = "";
        named = true;
      } else if (normalized.startsWith(name + " ")) {
        normalized = normalized.slice(name.length + 1);
        named = true;
      } else if (normalized.endsWith(" " + name)) {
        normalized = normalized.slice(0, -name.length - 1);
        named = true;
      }
    }
    if (
      /^(?:thank you(?: very much)?|thanks(?: a lot)?)(?: |$)/.test(normalized)
    ) {
      normalized = normalized.replace(
        /^(?:thank you(?: very much)?|thanks(?: a lot)?)(?: |$)/,
        "",
      );
      thanked = true;
    }
    if (/ (?:thank you(?: very much)?|thanks(?: a lot)?)$/.test(normalized)) {
      normalized = normalized.replace(
        / (?:thank you(?: very much)?|thanks(?: a lot)?)$/,
        "",
      );
      thanked = true;
    }
    normalized = normalized.trim();
    if (normalized === before) break;
  }
  if (!normalized) return named && thanked;
  return /^(?:(?:please|(?:can|could|would) you(?: please)?|i (?:need|want)(?: you)? to) )?(?:stop listening|end (?:the |this )?conversation|goodbye|bye(?: bye)?|that(?:'s| is| would be| will be|'ll be) (?:all|it|everything)|i(?:'m| am) done|we(?:'re| are) done|nothing else|no more questions)(?: for (?:now|today))?$/.test(
    normalized,
  );
}

export class ConversationIdle {
  constructor(onTimeout, now = () => Date.now()) {
    this.onTimeout = onTimeout;
    this.now = now;
    this.running = false;
    this.seconds = 30;
  }
  configure(seconds) {
    this.seconds = [0, 30, 60, 120].includes(Number(seconds))
      ? Number(seconds)
      : 30;
    this.activity();
  }
  start(seconds) {
    this.running = true;
    this.configure(seconds);
  }
  activity() {
    if (this.running) this.deadline = this.now() + this.seconds * 1000;
  }
  stop() {
    this.running = false;
    this.deadline = null;
  }
  tick({ mode, inputActive = false, outputActive = false }) {
    if (!this.running || !this.seconds) return null;
    if (mode !== "listening" || inputActive || outputActive) this.activity();
    const remaining = Math.max(
      0,
      Math.ceil((this.deadline - this.now()) / 1000),
    );
    if (!remaining) {
      this.stop();
      this.onTimeout();
    }
    return remaining;
  }
}

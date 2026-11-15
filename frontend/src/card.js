import { AgentSession } from "@fishaudio/agent-client";
import {
  MicController,
  microphoneMuted,
  microphoneToggle,
} from "./controls.js";
import { ConversationIdle, isEndRequest } from "./idle.js";

const VOICES = [
  "Clara",
  "Nora",
  "Harper",
  "Patricia",
  "Owen",
  "Marco",
  "Milo",
  "Jonah",
];
const DEFAULT_PERSONALITY =
  "You are Jarvis, a calm, capable household assistant inspired by Iron Man's JARVIS. Be concise, composed and quietly witty. Do not narrate routine actions or tool calls. Avoid fillers such as 'Let me check' and 'One moment'. Silently use the tools, then give one brief result. Ask for clarification only when needed.";

const style = `
:host{display:block;color:var(--primary-text-color,#eef2fa);font:15px/1.5 system-ui,sans-serif;color-scheme:dark}*{box-sizing:border-box}
.shell{background:var(--ha-card-background,#111923);border:1px solid var(--divider-color,#2a3545);border-radius:22px;padding:25px;max-width:940px;margin:auto;box-shadow:0 16px 48px #0002}
header{display:flex;align-items:center;gap:13px}.mark{width:45px;height:45px;display:grid;place-items:center;border-radius:15px;background:#51dbc31b;color:#70ebd4;font-size:25px}.title{margin:0;font-size:25px;font-weight:680;letter-spacing:-.5px}.subtitle,.hint{color:var(--secondary-text-color,#a5b1c3);font-size:13px;margin:2px 0}.spacer{flex:1}
button,select,input,textarea{font:inherit}textarea{width:100%;min-height:160px;background:#101a27;color:#eef2fa;border:1px solid #3b4a5f;border-radius:10px;padding:10px;resize:vertical}input[type=checkbox]{display:inline!important;width:auto!important;margin-right:8px!important}button,select{border:1px solid #3b4a5f;border-radius:11px;background:#233044;color:#eef2fa;padding:11px 16px}button{cursor:pointer;touch-action:none}button:hover{background:#304159}button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid #79ead4;outline-offset:3px}button:disabled{opacity:.4;cursor:default}.primary{background:#77e3cd;color:#102825;border-color:transparent;font-weight:650}.primary:hover{background:#9beedc}.danger{background:#482936;border-color:#7b3e52}.icon{padding:9px 13px}
.stage{text-align:center;padding:30px 0 20px}.orb{width:104px;height:104px;border-radius:50%;margin:0 auto 18px;background:radial-gradient(circle at 35% 30%,#7ae7d3,#287a86 60%,#23394e);box-shadow:0 0 0 12px #5dd9ca0a,0 0 45px #5dd9ca20;transition:transform .2s}.orb.live{animation:breathe 2.5s ease-in-out infinite}.orb.muted{filter:saturate(.2)}@keyframes breathe{50%{transform:scale(1.04);box-shadow:0 0 0 18px #5dd9ca0a,0 0 65px #5dd9ca30}}.state{font-size:19px;margin:0;font-weight:600}.pill{display:inline-flex;align-items:center;gap:7px;margin-top:8px;border-radius:20px;background:#293545;padding:4px 10px;font-size:12px;color:#bbc8da}.dot{width:7px;height:7px;border-radius:50%;background:#78869a}.dot.on{background:#72e3cd}.dot.mute{background:#f7bd76}
.controls{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin:8px 0 15px}.mode{display:flex;justify-content:center;align-items:center;gap:10px;font-size:13px;color:#adbbce}.mode select{padding:7px 10px}.hold{display:block;margin:16px auto 0;min-width:225px;border-style:dashed}.hold.held{background:#4c7d72}.hidden{display:none!important}.notice{padding:13px 15px;border-radius:11px;background:#203648;color:#bed9eb;margin:16px 0;font-size:13px}.notice.error{background:#442d36;color:#ffced8}.conversation{margin-top:24px;border-top:1px solid #2b384b;padding-top:17px}.label{font-size:11px;letter-spacing:1.4px;text-transform:uppercase;color:#93a5bd}.transcript{height:220px;overflow:auto;scroll-behavior:smooth;padding:8px 0}.empty{color:#7889a1;font-size:14px;margin:25px 0;text-align:center}.bubble{padding:9px 13px;margin:8px 0;border-radius:12px;max-width:88%;background:#253449;white-space:pre-wrap;overflow-wrap:anywhere}.bubble.user{margin-left:auto;background:#27473f}.speaker{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#a3b5ca;display:block;margin-bottom:3px}.compose{display:flex;gap:8px}input{background:#101a27;color:#eef2fa;border:1px solid #3b4a5f;border-radius:10px;padding:11px;min-width:0;flex:1}.settings{margin-top:20px;padding:16px;border:1px solid #334259;border-radius:14px}.settings label{display:block;font-size:13px;margin-top:12px}.settings input{display:block;width:100%;margin:5px 0 10px}.settings .row{display:flex;gap:8px;flex-wrap:wrap}.link{color:#88e4d1;display:inline-block;margin-top:10px}.footer{display:flex;justify-content:space-between;gap:10px;font-size:11px;color:#8091aa;margin-top:17px}.tool{font-size:12px;color:#9dbbc8;min-height:19px;margin-top:10px}.timer{font-variant-numeric:tabular-nums}@media(max-width:520px){.shell{padding:18px;border-radius:16px}.title{font-size:22px}.controls button{padding:11px 12px}.transcript{height:200px}.footer{display:block}}
`;

export class HouseTalkCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.epoch = 0;
    this.session = null;
    this.bridgeId = null;
    this.transcript = new Map();
    this.mic = new MicController(async (muted) => {
      if (this.session) await this.session.setMicMuted(muted);
      this.draw();
    });
    this.timeoutSeconds = 30;
    try {
      const saved = localStorage.getItem("house-talk-idle-seconds");
      if (saved !== null && [0, 30, 60, 120].includes(Number(saved)))
        this.timeoutSeconds = Number(saved);
    } catch {}
    this.enabled = true;
    this.voice = "Clara";
    this.personality = DEFAULT_PERSONALITY;
    try {
      const mode = localStorage.getItem("house-talk-mode");
      if (["handsfree", "ptt"].includes(mode)) this.mic.state.mode = mode;
      const voice = localStorage.getItem("house-talk-voice");
      if (VOICES.includes(voice)) this.voice = voice;
      this.personality =
        localStorage.getItem("house-talk-personality") || DEFAULT_PERSONALITY;
    } catch {}
    this.idle = new ConversationIdle(() =>
      this.end(
        `Conversation ended after ${this.timeoutSeconds} seconds of inactivity.`,
      ),
    );
    this.release = () => {
      if (this.mic.state.held)
        this.mic.update({ held: false }).catch((e) => this.fail(e));
      this.draw();
    };
    this.keydown = (e) => {
      if (
        e.code === "Space" &&
        !e.repeat &&
        this.session &&
        this.mic.state.mode === "ptt" &&
        !["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(
          this.shadowRoot.activeElement?.tagName,
        )
      ) {
        e.preventDefault();
        this.mic.update({ held: true }).catch((e) => this.fail(e));
        this.draw();
      }
    };
    this.keyup = (e) => {
      if (e.code === "Space") this.release();
    };
    this.render();
  }
  setConfig(config) {
    this.config = config;
  }
  getCardSize() {
    return 9;
  }
  set hass(value) {
    this._hass = value;
    if (!this.checked) {
      this.checked = true;
      this.refresh();
    }
  }
  set bridge(value) {
    this._bridge = value;
    this.refresh();
    this.loadDesktop().catch((error) => this.fail(error));
  }
  connectedCallback() {
    window.addEventListener("blur", this.release);
    window.addEventListener("keydown", this.keydown);
    window.addEventListener("keyup", this.keyup);
    document.addEventListener("visibilitychange", this.release);
  }
  disconnectedCallback() {
    window.removeEventListener("blur", this.release);
    window.removeEventListener("keydown", this.keydown);
    window.removeEventListener("keyup", this.keyup);
    document.removeEventListener("visibilitychange", this.release);
    this.end();
  }
  $(id) {
    return this.shadowRoot.getElementById(id);
  }
  rpc(type, params = {}) {
    if (this._bridge) return this._bridge.call(type, params);
    return this._hass.callWS({ type: `fish_live3/${type}`, ...params });
  }
  async refresh() {
    try {
      this.status = await this.rpc("status");
      this.notice(
        this.status.configured
          ? window.isSecureContext
            ? ""
            : "For microphone access, open this dashboard using your Home Assistant HTTPS address, or use the Windows app."
          : "Add the Fish Live3 integration in Settings → Devices & services, then enter your Fish API key.",
      );
    } catch (error) {
      this.status = { configured: false };
      this.notice(
        this._bridge
          ? "Open Settings and connect HouseTalk to Home Assistant."
          : error?.message ||
              "Could not reach the Fish Live3 integration. Check Home Assistant → Settings → Devices & services.",
      );
    }
    this.draw();
    this.connectionText();
  }
  render() {
    this.shadowRoot.innerHTML = `<style>${style}</style><section class="shell">
    <header><div class="mark" aria-hidden="true">⌁</div><div><h1 class="title">House Talk</h1><p class="subtitle">Your home, in conversation</p></div><div class="spacer"></div><button id="settingsButton" class="icon" aria-label="Settings">⚙</button></header>
    <div id="notice" class="notice hidden" role="status"></div>
    <div class="stage"><div id="orb" class="orb" aria-hidden="true"></div><p id="state" class="state">Ready when you are</p><div class="pill"><span id="dot" class="dot"></span><span id="micState">Microphone off</span></div></div>
    <div class="controls"><button id="start" class="primary">Start conversation</button><button id="mute" disabled>Mute microphone</button><button id="end" class="danger" disabled>End conversation</button></div>
    <div class="mode"><label for="mode">Microphone mode</label><select id="mode"><option value="handsfree">Hands-free</option><option value="ptt">Push-to-talk</option></select></div>
    <button id="hold" class="hold hidden" disabled>Hold to talk · Space</button><p id="modeHint" class="hint" style="text-align:center;margin-top:12px">Listening stays on until you mute or end the conversation.</p>
    <div class="mode" style="margin-top:12px"><label for="idleTimeout">Auto-end after</label><select id="idleTimeout"><option value="30">30 seconds of quiet</option><option value="60">1 minute of quiet</option><option value="120">2 minutes of quiet</option><option value="0">Off · end manually</option></select></div><p id="idleHint" class="hint" style="text-align:center;margin-top:8px">Say “stop listening” or “end conversation” to finish now.</p>
    <div id="settings" class="settings hidden"><div class="label">Connections</div><div id="connectionText" class="hint"></div><label for="voice">Voice (next conversation)</label><select id="voice"><option value="Clara">Clara</option><option value="Nora">Nora</option><option value="Harper">Harper</option><option value="Patricia">Patricia</option><option value="Owen">Owen</option><option value="Marco">Marco</option><option value="Milo">Milo</option><option value="Jonah">Jonah</option></select><label for="personality">Personality instructions (next conversation)</label><textarea id="personality" maxlength="8000"></textarea><button id="savePersonality">Save personality</button><div id="desktopSettings" class="hidden"><label><input id="enabled" type="checkbox" checked>HouseTalk enabled</label><label><input id="runOnLogin" type="checkbox">Run on Windows login</label><p id="installLocation" class="hint"></p><button id="trayMenu">Open tray menu</button><label for="haUrl">Home Assistant address</label><input id="haUrl" type="url" placeholder="http://homeassistant.local:8123"><div class="row"><button id="login">Connect Home Assistant</button></div><label for="wakePhrase">Wake phrase (Windows)</label><input id="wakePhrase" value="Hey House" maxlength="50"><div class="row"><button id="wake">Enable wake word</button><button id="saveWake">Save wake phrase</button></div><p id="wakeStatus" class="hint">Wake-word listening is local and off by default.</p></div><a id="integrationLink" class="link" href="/config/integrations/dashboard?domain=fish_live3">Open Fish integration settings</a><p class="hint" style="margin-top:9px">Fish API key: Home Assistant → Settings → Devices & services → Fish Live3. No key belongs in this card or app.</p></div>
    <div class="conversation"><span class="label">Conversation</span><div id="transcript" class="transcript" aria-live="polite"><p class="empty">Speak naturally, interrupt, or type a message.</p></div><form id="compose" class="compose"><input id="message" aria-label="Message" placeholder="Or type to your assistant…" maxlength="2000"><button id="send" type="submit" disabled>Send</button></form><div id="tool" class="tool"></div></div>
    <div class="footer"><span>Fish Live3 · English · via Home Assistant</span><span id="timer" class="timer">Not connected</span></div>
  </section>`;
    this.$("start").onclick = () => this.start();
    this.$("end").onclick = () => this.end();
    this.$("mute").onclick = () => this.toggleMicrophone();
    this.$("mode").value = this.mic.state.mode;
    this.$("mode").onchange = async () => {
      try {
        await this.mic.update({
          mode: this.$("mode").value,
          muted: false,
          held: false,
        });
        await this.savePreferences({ microphoneMode: this.mic.state.mode });
      } catch (error) {
        this.fail(error);
      }
      this.draw();
    };
    this.$("idleTimeout").value = String(this.timeoutSeconds);
    this.$("idleTimeout").onchange = () => {
      this.timeoutSeconds = Number(this.$("idleTimeout").value);
      try {
        localStorage.setItem(
          "house-talk-idle-seconds",
          String(this.timeoutSeconds),
        );
      } catch {}
      this.idle.configure(this.timeoutSeconds);
      this.savePreferences({ idleSeconds: this.timeoutSeconds }).catch(
        (error) => this.fail(error),
      );
      this.draw();
    };
    this.$("hold").onpointerdown = (e) => {
      if (!this.session || this.mic.state.muted) return;
      e.preventDefault();
      this.$("hold").setPointerCapture(e.pointerId);
      this.mic.update({ held: true }).catch((e) => this.fail(e));
      this.draw();
    };
    for (const event of ["pointerup", "pointercancel", "lostpointercapture"])
      this.$("hold").addEventListener(event, this.release);
    this.$("settingsButton").onclick = () => {
      this.$("settings").classList.toggle("hidden");
      this.loadDesktop();
    };
    this.$("compose").onsubmit = (e) => {
      e.preventDefault();
      const text = this.$("message").value.trim();
      if (!text || !this.session) return;
      if (isEndRequest(text, this.$("wakePhrase").value)) {
        this.$("message").value = "";
        this.end("Conversation ended by request.");
        return;
      }
      this.idle.activity();
      this.session.sendUserMessage(text, { audio: true });
      this.$("message").value = "";
    };
    this.$("message").oninput = () => {
      this.idle.activity();
      this.session?.sendUserActivity();
    };
    this.$("login").onclick = async () => {
      try {
        await this._bridge.host("connect", { url: this.$("haUrl").value });
        await this.refresh();
      } catch (e) {
        this.fail(e);
      }
    };
    this.$("voice").value = this.voice;
    this.$("personality").value = this.personality;
    this.$("voice").onchange = () => {
      this.voice = this.$("voice").value;
      this.savePreferences({ voice: this.voice })
        .then(() => this.notice("Voice saved for the next conversation."))
        .catch((error) => this.fail(error));
    };
    this.$("savePersonality").onclick = () => {
      this.personality =
        this.$("personality").value.trim() || DEFAULT_PERSONALITY;
      this.savePreferences({ personality: this.personality })
        .then(() => this.notice("Personality saved for the next conversation."))
        .catch((error) => this.fail(error));
    };
    this.$("trayMenu").onclick = () =>
      this._bridge.host("trayMenu", {}).catch((error) => this.fail(error));
    this.$("enabled").onchange = () =>
      this.savePreferences({ enabled: this.$("enabled").checked }).catch(
        (error) => this.fail(error),
      );
    this.$("runOnLogin").onchange = () =>
      this.savePreferences({ runOnLogin: this.$("runOnLogin").checked }).catch(
        (error) => this.fail(error),
      );
    this.$("wake").onclick = async () => {
      try {
        await this.applyDesktopSettings(
          await this._bridge.host("wake", {
            enabled: !this.wakeEnabled,
            phrase: this.$("wakePhrase").value,
          }),
        );
      } catch (error) {
        this.fail(error);
      }
    };
    this.$("saveWake").onclick = async () => {
      try {
        await this.applyDesktopSettings(
          await this._bridge.host("wake", {
            enabled: !!this.wakeEnabled,
            phrase: this.$("wakePhrase").value,
          }),
        );
        this.notice("Wake phrase saved.");
      } catch (error) {
        this.fail(error);
      }
    };
  }
  async savePreferences(patch) {
    if (this._bridge?.host) {
      await this.applyDesktopSettings(
        await this._bridge.host("preferences", patch),
      );
      return;
    }
    const names = {
      microphoneMode: "mode",
      voice: "voice",
      personality: "personality",
      idleSeconds: "idle-seconds",
    };
    for (const [key, value] of Object.entries(patch)) {
      if (names[key])
        try {
          localStorage.setItem("house-talk-" + names[key], String(value));
        } catch {}
    }
  }
  async toggleMicrophone() {
    if (!this.session || this.micPending) return;
    this.micPending = true;
    const patch = microphoneToggle(this.mic.state);
    if (patch.mode) this.$("mode").value = patch.mode;
    this.draw();
    try {
      await this.mic.update(patch);
      await this.savePreferences({ microphoneMode: this.mic.state.mode });
    } catch (error) {
      this.fail(error);
    } finally {
      this.micPending = false;
      this.draw();
    }
  }
  async loadDesktop() {
    this.connectionText();
    if (!this._bridge?.host) return;
    await this.applyDesktopSettings(await this._bridge.host("settings", {}));
    this.$("desktopSettings").classList.remove("hidden");
    this.$("integrationLink").href = "#";
    this.$("integrationLink").onclick = (event) => {
      event.preventDefault();
      this._bridge.host("openSettings", {});
    };
  }
  async applyDesktopSettings(config) {
    this.desktopConfig = config;
    this.enabled = config.enabled !== false;
    this.$("enabled").checked = this.enabled;
    this.$("runOnLogin").checked = !!config.runOnLogin;
    this.$("haUrl").value = config.url || "";
    this.$("installLocation").textContent = config.installLocation
      ? "Installed in " + config.installLocation
      : "";
    this.wakeEnabled = !!config.wakeEnabled;
    this.$("wakePhrase").value = config.wakePhrase || "Hey House";
    this.$("wake").textContent = this.wakeEnabled
      ? "Disable wake word"
      : "Enable wake word";
    this.$("wake").disabled = !config.wakeAvailable || !this.enabled;
    if (VOICES.includes(config.voice)) {
      this.voice = config.voice;
      this.$("voice").value = this.voice;
    }
    if (typeof config.personality === "string") {
      this.personality = config.personality;
      this.$("personality").value = this.personality;
    }
    if (
      [0, 30, 60, 120].includes(config.idleSeconds) &&
      this.timeoutSeconds !== config.idleSeconds
    ) {
      this.timeoutSeconds = config.idleSeconds;
      this.$("idleTimeout").value = String(this.timeoutSeconds);
      this.idle.configure(this.timeoutSeconds);
    }
    if (
      ["handsfree", "ptt"].includes(config.microphoneMode) &&
      this.mic.state.mode !== config.microphoneMode
    ) {
      this.$("mode").value = config.microphoneMode;
      try {
        await this.mic.update({
          mode: config.microphoneMode,
          muted: false,
          held: false,
        });
      } catch (error) {
        this.fail(error);
      }
    }
    if (!this.enabled && (this.session || this.starting))
      await this.end("HouseTalk is disabled.");
    this.draw();
  }
  connectionText() {
    this.$("connectionText").textContent = this.status?.configured
      ? `Connected to ${this.status.name} · ${this.status.voice}`
      : this._bridge
        ? "Connect this app to Home Assistant below."
        : "Home Assistant integration needs setup.";
  }
  notice(text, error = false) {
    this.$("notice").textContent = text;
    this.$("notice").className =
      "notice" + (error ? " error" : "") + (text ? "" : " hidden");
  }
  fail(error) {
    this.notice(error?.message || String(error), true);
  }
  put(id, role, text) {
    this.transcript.set(id, { role, text });
    const box = this.$("transcript");
    box.replaceChildren();
    for (const item of this.transcript.values()) {
      const bubble = document.createElement("div");
      bubble.className = "bubble " + item.role;
      const who = document.createElement("span");
      who.className = "speaker";
      who.textContent = item.role === "user" ? "You" : "House Talk";
      bubble.append(who, document.createTextNode(item.text));
      box.append(bubble);
    }
    box.scrollTop = box.scrollHeight;
  }
  userTranscript(event, epoch) {
    if (epoch !== this.epoch) return;
    this.put("user-" + event.segmentId, "user", event.text);
    this.idle.activity();
    if (event.final && isEndRequest(event.text, this.$("wakePhrase").value))
      this.end("Conversation ended by voice.");
  }
  async start() {
    if (this.starting || this.session || !this.enabled) return;
    if (!window.isSecureContext) {
      this.notice(
        "Microphone access needs HTTPS. Open Home Assistant using its secure HTTPS address, or use the Windows app.",
        true,
      );
      return;
    }
    this.mic.state.muted = false;
    this.mic.state.held = false;
    const epoch = ++this.epoch;
    this.starting = true;
    this.notice("");
    this.mode = "connecting";
    this.draw();
    try {
      await this._bridge?.host?.("pauseWake", {});
      const prepared = await this.rpc(
        "session",
        this.status?.supports_preferences
          ? { voice: this.voice, personality: this.personality }
          : {},
      );
      if (epoch !== this.epoch) {
        await this.rpc("end", { bridge_id: prepared.bridge_id });
        return;
      }
      this.bridgeId = prepared.bridge_id;
      const handlers = {};
      for (const name of prepared.tools)
        handlers[name] = (params) => {
          if (epoch !== this.epoch) throw Error("Conversation ended");
          return this.rpc("tool", {
            bridge_id: prepared.bridge_id,
            name,
            params,
          });
        };
      const session = await AgentSession.start({
        sessionToken: prepared.session_token,
        microphone:
          this.mic.state.mode === "handsfree" && !this.mic.state.muted,
        clientTools: handlers,
        clientToolTimeoutMs: 30000,
        wakeLock: true,
        callbacks: {
          onModeChange: (mode) => {
            if (epoch === this.epoch) {
              this.mode = mode;
              this.idle.activity();
              this.draw();
            }
          },
          onUserTranscript: (e) => this.userTranscript(e, epoch),
          onAgentResponseDelta: (e) => {
            if (epoch === this.epoch) {
              this.idle.activity();
              this.put("agent-" + e.segmentId, "agent", e.text);
            }
          },
          onAgentResponse: (e) => {
            if (epoch === this.epoch) {
              this.idle.activity();
              this.put("agent-" + e.segmentId, "agent", e.text);
            }
          },
          onDisconnect: (e) => {
            if (epoch === this.epoch) this.end("Call ended: " + e.reason);
          },
          onError: (e) => this.fail(e),
          onToolCallStarted: (e) => {
            this.$("tool").textContent =
              e.toolName === "home_assistant"
                ? "Asking your home…"
                : "Checking your exposed devices…";
          },
          onToolCallCompleted: () => {
            this.$("tool").textContent = "Home Assistant replied";
          },
          onToolCallFailed: () => {
            this.$("tool").textContent =
              "Home Assistant could not complete that request";
          },
        },
      });
      if (epoch !== this.epoch) {
        await session.end();
        return;
      }
      this.session = session;
      this.startedAt = Date.now();
      this.mode = session.mode;
      await this.mic.update({ active: true, held: false });
      this.idle.start(this.timeoutSeconds);
      this.idleRemaining = this.timeoutSeconds;
      this.clock = setInterval(() => {
        if (this.session) {
          this.idleRemaining = this.idle.tick({
            mode: this.mode,
            inputActive:
              this.mic.state.held ||
              (!microphoneMuted(this.mic.state) &&
                this.session.getInputVolume() > 0.02),
            outputActive: this.session.getOutputVolume() > 0.02,
          });
          this.draw();
        }
      }, 500);
      this.draw();
    } catch (error) {
      await this.end();
      this.fail(error);
    } finally {
      this.starting = false;
      this.draw();
    }
  }
  async end(message = "") {
    ++this.epoch;
    this.starting = false;
    this.idle.stop();
    const session = this.session,
      bridgeId = this.bridgeId;
    this.session = null;
    this.bridgeId = null;
    clearInterval(this.clock);
    this.mic.update({ active: false, held: false });
    this.mode = "idle";
    this.draw();
    // Revoke local tool access at the same time as ending the media session.
    await Promise.allSettled([
      session?.end(),
      bridgeId ? this.rpc("end", { bridge_id: bridgeId }) : Promise.resolve(),
    ]);
    if (message) this.notice(message);
    await this._bridge?.host?.("resumeWake", {});
  }
  draw() {
    const active = !!this.session,
      muted = microphoneMuted(this.mic.state),
      ptt = this.mic.state.mode === "ptt";
    if (this._bridge && this.wakeEnabled)
      this.$("wakeStatus").textContent =
        active || this.starting
          ? "Wake-word listening pauses during this conversation."
          : "Listening locally for " + this.$("wakePhrase").value;
    this.$("start").disabled =
      this.starting ||
      active ||
      !this.status?.configured ||
      !this.enabled ||
      !!(this._bridge && !this.desktopConfig);
    this.$("end").disabled = !active && !this.starting;
    this.$("mute").disabled = !active || this.micPending;
    this.$("send").disabled = !active;
    this.$("hold").disabled = !active || this.mic.state.muted;
    this.$("hold").classList.toggle("hidden", !ptt);
    this.$("hold").classList.toggle("held", this.mic.state.held);
    this.$("mute").textContent = !active
      ? "Microphone off"
      : this.micPending
        ? "Updating microphone…"
        : muted
          ? "Unmute microphone"
          : "Mute microphone";
    this.$("modeHint").textContent = ptt
      ? "Hold the button or Space to speak. Release to mute."
      : "Speak freely while the conversation is open.";
    this.$("idleHint").textContent =
      active && this.timeoutSeconds && this.mode === "listening"
        ? `Auto-end in ${this.idleRemaining ?? this.timeoutSeconds}s of quiet · say “stop listening” to end now.`
        : "Say “stop listening” or “end conversation” to finish now.";
    this.$("state").textContent = this.starting
      ? "Connecting…"
      : !active
        ? this.enabled
          ? "Ready when you are"
          : "HouseTalk disabled"
        : this.mode === "speaking"
          ? "Your home is speaking"
          : this.mode === "thinking"
            ? "Thinking…"
            : muted
              ? ptt && !this.mic.state.muted
                ? "Ready — hold to talk"
                : "Conversation paused"
              : "Listening to you";
    this.$("micState").textContent = !active
      ? this._bridge && this.wakeEnabled && this.enabled
        ? "Local wake word only"
        : "Microphone off"
      : muted
        ? ptt && !this.mic.state.muted
          ? "Push-to-talk · release mutes"
          : "Microphone muted"
        : "Microphone live";
    this.$("dot").className = "dot" + (active ? (muted ? " mute" : " on") : "");
    this.$("orb").className =
      "orb" + (active && !muted ? " live" : active ? " muted" : "");
    this.$("voice").disabled = !this.status?.supports_preferences;
    this.$("savePersonality").disabled = !this.status?.supports_preferences;
    if (this._bridge?.host) {
      const state = JSON.stringify({ active, micMuted: muted });
      if (this.lastHostState !== state) {
        this.lastHostState = state;
        this._bridge.host("state", { active, micMuted: muted }).catch(() => {});
      }
    }
    if (active) {
      const seconds = Math.floor((Date.now() - this.startedAt) / 1000);
      this.$("timer").textContent =
        `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")} · 60-minute service limit`;
    } else this.$("timer").textContent = "Not connected";
  }
}
if (!customElements.get("house-talk-card"))
  customElements.define("house-talk-card", HouseTalkCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "house-talk-card",
  name: "House Talk · Fish Live3",
  description:
    "Live conversation with your Home Assistant. Start, mute, push-to-talk and end controls.",
});

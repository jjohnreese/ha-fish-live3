import test from "node:test";
import assert from "node:assert/strict";
import {
  MicController,
  microphoneMuted,
  microphoneToggle,
} from "./src/controls.js";
test("idle microphone is always off", () =>
  assert.equal(
    microphoneMuted({
      active: false,
      mode: "handsfree",
      muted: false,
      held: true,
    }),
    true,
  ));
test("push to talk release mutes", async () => {
  const states = [];
  const mic = new MicController(async (m) => states.push(m));
  await mic.update({ active: true, mode: "ptt" });
  await mic.update({ held: true });
  await mic.update({ held: false });
  assert.deepEqual(states, [true, false, true]);
});
test("manual mute overrides a held PTT button", () =>
  assert.equal(
    microphoneMuted({ active: true, mode: "ptt", muted: true, held: true }),
    true,
  ));
test("a quick release cannot leave a queued unmute behind", async () => {
  const states = [];
  const mic = new MicController(async (m) => states.push(m));
  mic.update({ active: true, mode: "ptt", held: true });
  await mic.update({ held: false });
  assert.deepEqual(states, [true, true]);
});
test("end wins over an in-flight press", async () => {
  const states = [];
  const mic = new MicController(async (m) => states.push(m));
  mic.update({ active: true, mode: "ptt", held: true });
  await mic.update({ active: false, held: false });
  assert(states.every(Boolean));
});

test("explicit unmute from PTT really opens the microphone", async () => {
  const applied = [];
  const mic = new MicController(async (muted) => applied.push(muted));
  await mic.update({ active: true, mode: "ptt" });
  await mic.update(microphoneToggle(mic.state));
  assert.equal(mic.state.mode, "handsfree");
  assert.equal(applied.at(-1), false);
});
test("permission failure restores a muted state and permits retry", async () => {
  let denied = true;
  const mic = new MicController(async (muted) => {
    if (!muted && denied) throw Error("Permission denied");
  });
  await mic.update({ active: true, mode: "ptt" });
  await assert.rejects(mic.update(microphoneToggle(mic.state)));
  assert.equal(microphoneMuted(mic.state), true);
  denied = false;
  await mic.update(microphoneToggle(mic.state));
  assert.equal(microphoneMuted(mic.state), false);
});

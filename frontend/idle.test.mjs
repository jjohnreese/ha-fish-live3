import test from "node:test";
import assert from "node:assert/strict";
import { ConversationIdle, isEndRequest } from "./src/idle.js";

function clock() {
  let time = 0,
    ended = 0;
  const timer = new ConversationIdle(
    () => ended++,
    () => time,
  );
  return { timer, at: (t) => (time = t), ended: () => ended };
}
test("30 seconds of idle ends once", () => {
  const c = clock();
  c.timer.start(30);
  c.at(29999);
  assert.equal(c.timer.tick({ mode: "listening" }), 1);
  c.at(30000);
  c.timer.tick({ mode: "listening" });
  c.timer.tick({ mode: "listening" });
  assert.equal(c.ended(), 1);
});
test("thinking, speaking and audio reset the idle deadline", () => {
  for (const state of [
    { mode: "thinking" },
    { mode: "speaking" },
    { mode: "listening", inputActive: true },
    { mode: "listening", outputActive: true },
  ]) {
    const c = clock();
    c.timer.start(30);
    c.at(45000);
    c.timer.tick(state);
    assert.equal(c.ended(), 0);
    c.at(74000);
    assert.equal(c.timer.tick({ mode: "listening" }), 1);
    c.at(75000);
    c.timer.tick({ mode: "listening" });
    assert.equal(c.ended(), 1);
  }
});
test("new transcript or typed activity gets a fresh interval", () => {
  const c = clock();
  c.timer.start(30);
  c.at(29000);
  c.timer.activity();
  c.at(30000);
  assert.equal(c.timer.tick({ mode: "listening" }), 29);
  assert.equal(c.ended(), 0);
});
test("manual end and disabled timeout never auto-end", () => {
  const c = clock();
  c.timer.start(30);
  c.timer.stop();
  c.at(90000);
  c.timer.tick({ mode: "listening" });
  c.timer.start(0);
  c.at(190000);
  c.timer.tick({ mode: "listening" });
  assert.equal(c.ended(), 0);
});
test("changing timeout resets it and a new call has no old deadline", () => {
  const c = clock();
  c.timer.start(30);
  c.at(29000);
  c.timer.configure(60);
  c.at(89000);
  c.timer.tick({ mode: "listening" });
  assert.equal(c.ended(), 1);
  c.at(100000);
  c.timer.start(30);
  assert.equal(c.timer.tick({ mode: "listening" }), 30);
});
test("voice end commands accept polite forms but reject unrelated speech", () => {
  for (const text of [
    "Stop listening.",
    "end conversation",
    "End the conversation!",
    "goodbye",
    "Okay, I need to stop listening.",
    "End con-conversation.",
    "Could you please stop listening?",
    "Please end the conversation now.",
  ])
    assert.ok(isEndRequest(text), text);
  for (const text of [
    "don't stop listening",
    "how do I end conversation",
    "stop listening to music",
    "goodbye to my friend",
  ])
    assert.equal(isEndRequest(text), false, text);
});
test("natural closing phrases and thanks with the configured wake name end the call", () => {
  for (const text of [
    "Thank you, Jarvis.",
    "Thanks Jarvis",
    "Thank you, that would be all.",
    "That’s it. Thank you.",
    "That will be all, thank you.",
    "Okay, Jarvis, that’s all for now.",
    "Jarvis, please end this conversation.",
    "Thanks a lot, Jarvis",
    "I am done",
    "Nothing else, thanks",
  ])
    assert.ok(isEndRequest(text, "Jarvis"), text);
  assert.ok(isEndRequest("Thank you, House.", "Hey House"));
  assert.ok(isEndRequest("Thanks Atlas", "Atlas"));
  assert.equal(isEndRequest("Thanks Jarvis", "Atlas"), false);
});
test("ordinary thanks and ongoing requests do not end a call", () => {
  for (const text of [
    "Thank you",
    "thanks",
    "thank you Jarvis can you turn on the light",
    "Jarvis",
    "that’s all I need to know about the kitchen",
    "nothing else is on",
    "thanks for checking",
    "please do not stop listening",
  ])
    assert.equal(isEndRequest(text, "Jarvis"), false, text);
});

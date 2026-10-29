// Changing the font by asking in words. With an Anthropic API key, Claude reads the request and
// answers with the new settings (through a tool whose input is the settings). Without a key,
// simple requests are understood here: "עבה יותר", "צר מאוד", "האות ש רחבה יותר", "נטוי".
(function () {
  "use strict";

  const MODEL = "claude-opus-5-5";

  // ---------------------------------------------------------------- simple requests, no key

  const WORDS = [
    { key: "weight", up: ["עבה", "עבות", "מודגש", "מודגשת", "כבד", "כבדה", "שמן", "שמנה", "בולט", "בולטת", "חזק"], down: ["דק", "דקה", "דקות", "רזה", "עדין", "עדינה", "קל", "קלה", "בהיר"] },
    { key: "width", up: ["רחב", "רחבה", "רחבות", "רחבים"], down: ["צר", "צרה", "צרות", "צרים", "דחוס", "דחוסה"] },
    { key: "height", up: ["גבוה", "גבוהה", "גבוהות", "גדול", "גדולה", "גדולות"], down: ["נמוך", "נמוכה", "נמוכות", "קטן", "קטנה", "קטנות"] },
    { key: "slant", up: ["נטוי", "נטויה", "נטויות", "נוטה", "אלכסוני"], zero: ["ישר", "ישרה", "זקוף", "זקופה"] },
    { key: "round", up: ["עגול", "עגולה", "עגולות", "מעוגל", "מעוגלת", "רך", "רכה"], down: ["חד", "חדה", "חדות", "מחודד"] },
    { key: "spacing", up: ["מרווח", "מרווחת", "מרווחות", "פזור", "מפוזר", "אוורירי"], down: ["צפוף", "צפופה", "צפופות", "צמוד", "צמודה", "צמודות"] },
    { key: "contrast", up: ["ניגודיות", "קונטרסט"], down: ["אחיד", "אחידה", "אחידות"] },
    { key: "shift", up: ["למעלה"], down: ["למטה"], letterOnly: true },
  ];

  function hasWord(text, w) {
    return new RegExp("(^|[^א-ת])(ו|ה|ש|ול|יותר )?" + w + "($|[^א-ת])").test(text);
  }

  // "האות ש", "את ה־ש", "האותיות ש ו־ל": the letters a request is about.
  function lettersIn(text) {
    const out = [];
    const re = /(?:האותיות|האות|אות|אותיות|את ה[־-]?|ה[־-])\s*((?:[א-ת](?:[׳']|\s|,|ו[־-]?)*)+)/g;
    let m;
    while ((m = re.exec(text))) {
      for (const ch of m[1].replace(/ו[־-]/g, " ").split(/[\s,]+/)) {
        if (/^[א-ת]$/.test(ch)) out.push(ch);
      }
    }
    return [...new Set(out)];
  }

  // ctx: {keys: [{key, min, max, step, value}], letterKeys: [{key, min, max, step}] | null,
  //       letterValue(letter, key)}
  function simple(text, ctx) {
    // each part of the request on its own: "עבה יותר, והאות ש רחבה" is two changes
    const parts = text.split(/[,.;!?\n]+| ו(?=(?:האות|האותיות|את ה|ה[־-]))/).filter((p) => p.trim());
    const out = { settings: [], letters: [], explanation: "" };
    for (const p of parts) {
      const r = simplePart(p, ctx);
      out.settings.push(...r.settings);
      out.letters.push(...r.letters);
    }
    if (!out.settings.length && !out.letters.length) {
      out.explanation = "לא הבנתי מה לשנות. אפשר לכתוב למשל: \"עבה יותר\", \"צר מאוד\", \"נטוי\", \"עגול יותר\", \"האות ש רחבה יותר\". עם מפתח API אפשר לכתוב כל בקשה במילים חופשיות.";
    }
    return out;
  }

  function simplePart(text, ctx) {
    const t = " " + text + " ";
    const amount = /מאוד|הרבה|ממש|לגמרי/.test(t) ? 2 : /קצת|מעט|טיפה|קצת יותר/.test(t) ? 0.5 : 1;
    const less = /פחות/.test(t) ? -1 : 1;
    const letters = ctx.letterKeys ? lettersIn(t) : [];
    const settings = [], letterChanges = [];
    for (const w of WORDS) {
      let dir = 0;
      if (w.up.some((x) => hasWord(t, x))) dir = 1;
      if (w.down && w.down.some((x) => hasWord(t, x))) dir = -1;
      const zero = w.zero && w.zero.some((x) => hasWord(t, x));
      if (!dir && !zero) continue;
      dir *= less;
      if (letters.length && ctx.letterKeys) {
        const lk = ctx.letterKeys.find((k) => k.key === w.key);
        if (!lk) continue;
        for (const L of letters) {
          const v = ctx.letterValue(L, w.key);
          letterChanges.push({ letter: L, key: w.key, value: clamp(zero ? lk.base : v + dir * lk.step * amount, lk.min, lk.max) });
        }
      } else if (!w.letterOnly) {
        const k = ctx.keys.find((x) => x.key === w.key);
        if (!k) continue;
        settings.push({ key: w.key, value: clamp(zero ? 0 : k.value + dir * k.step * amount, k.min, k.max) });
      }
    }
    return { settings, letters: letterChanges };
  }

  function clamp(v, a, b) { return Math.min(b, Math.max(a, Math.round(v * 1000) / 1000)); }

  // ---------------------------------------------------------------- Claude

  function tool(ctx) {
    const props = {
      explanation: { type: "string", description: "One or two short sentences in Hebrew: what you changed and why." },
      settings: {
        type: "array",
        description: "Settings of the whole font to change, with their new values. Leave out settings that stay as they are.",
        items: {
          type: "object",
          properties: {
            key: { type: "string", enum: ctx.keys.map((k) => k.key) },
            value: { type: "number" },
          },
          required: ["key", "value"],
          additionalProperties: false,
        },
      },
      letters: {
        type: "array",
        description: ctx.letterKeys ? "Changes to single letters, with their new values. Empty when the request is about the whole font." : "Always empty in this mode.",
        items: {
          type: "object",
          properties: {
            letter: { type: "string", description: "One Hebrew letter, like ש or ך." },
            key: { type: "string", enum: (ctx.letterKeys || [{ key: "width" }]).map((k) => k.key) },
            value: { type: "number" },
          },
          required: ["letter", "key", "value"],
          additionalProperties: false,
        },
      },
    };
    return {
      name: "set_font",
      description: "Change the font being designed. Call it once with every change the request asks for.",
      strict: true,
      input_schema: { type: "object", properties: props, required: ["explanation", "settings", "letters"], additionalProperties: false },
    };
  }

  function describe(ctx) {
    const lines = ctx.keys.map((k) => `- ${k.key} (${k.label}): now ${k.value}, from ${k.min} to ${k.max}. ${k.about || ""}`);
    let s = "Settings of the whole font:\n" + lines.join("\n");
    if (ctx.letterKeys) {
      s += "\n\nSettings of a single letter (they multiply or add to the settings of the whole font):\n" +
        ctx.letterKeys.map((k) => `- ${k.key} (${k.label}): from ${k.min} to ${k.max}, ${k.base} means no change. ${k.about || ""}`).join("\n");
      const now = ctx.letterNow();
      if (now) s += "\n\nLetters already changed: " + now;
    }
    return s;
  }

  const SYSTEM = `You help a person who is not a type designer change a Hebrew font in a font maker program.
They write in Hebrew what they want changed; you call the set_font tool with the new values of the settings.

Change only what they asked for, and keep the font looking like a normal, readable font: unless they ask
for a strong change ("מאוד", "הרבה"), move a setting about a quarter of the way toward its end of the range.
"More" or "less" of something is relative to the value it has now. A request about some letters changes
only those letters. When a request can't be done with these settings, change nothing, and say in the
explanation what can be done instead.`;

  async function ask(text, ctx, apiKey, history) {
    const client = new Anthropic({ apiKey, dangerouslyAllowBrowser: true });
    const before = (history || []).slice(-4).map((h) => `Earlier request: ${h.text}\nWhat you did: ${h.explanation}`).join("\n\n");
    const response = await client.beta.messages.create({
      model: MODEL,
      max_tokens: 16000,
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
      output_config: { effort: "low" },
      system: SYSTEM + "\n\n" + (ctx.about || ""),
      tools: [tool(ctx)],
      tool_choice: { type: "auto" },
      messages: [{
        role: "user",
        content: `${describe(ctx)}\n\n${before ? before + "\n\n" : ""}The request: ${text}\n\nCall set_font with the changes.`,
      }],
    });
    if (response.stop_reason === "refusal") throw new Error("Claude לא הסכים לבקשה הזו.");
    const call = response.content.find((b) => b.type === "tool_use" && b.name === "set_font");
    if (!call) {
      const said = response.content.filter((b) => b.type === "text").map((b) => b.text).join(" ").trim();
      return { settings: [], letters: [], explanation: said || "לא היה מה לשנות." };
    }
    return check(call.input, ctx);
  }

  // The answer, kept to the settings there are and to their ranges.
  function check(input, ctx) {
    const out = { settings: [], letters: [], explanation: String((input && input.explanation) || "") };
    for (const s of (input && input.settings) || []) {
      const k = ctx.keys.find((x) => x.key === s.key);
      if (k && isFinite(s.value)) out.settings.push({ key: k.key, value: clamp(s.value, k.min, k.max) });
    }
    if (ctx.letterKeys) {
      for (const s of (input && input.letters) || []) {
        const k = ctx.letterKeys.find((x) => x.key === s.key);
        if (k && /^[א-ת]$/.test(s.letter) && isFinite(s.value)) out.letters.push({ letter: s.letter, key: k.key, value: clamp(s.value, k.min, k.max) });
      }
    }
    return out;
  }

  FontMaker.AI = { simple, ask, MODEL };
})();

# Estimated Fish Live3 API costs

**Last checked: November 15, 2026. All amounts are US dollars.**

Fish Audio's [Live3 page](https://fish.audio/live3/) advertises **$0.035 per minute**, a limited promotion ending **December 31, 2026**, against a listed regular rate of **$0.07 per minute**. The base agent rate includes speech recognition, the language model and speech synthesis. Check your own account before using the service; prices and eligibility can change.

HouseTalk is free software and collects no subscription fee or payment. You supply your own Fish API key, and Fish charges your account. This is an [unofficial personal project](../DISCLAIMER.md).

## Per conversation

The following arithmetic assumes the duration shown is billable. It excludes taxes and optional services. Values are rounded to the nearest cent, so very short calls are approximate.

| Billable duration | At promotional $0.035/min | At listed regular $0.07/min |
| --- | ---: | ---: |
| 30 seconds | $0.02 | $0.04 |
| 1 minute | $0.04 | $0.07 |
| 5 minutes | $0.18 | $0.35 |
| 10 minutes | $0.35 | $0.70 |
| 30 minutes | $1.05 | $2.10 |
| 60 minutes | $2.10 | $4.20 |

## Daily use over a 30-day month

| Total billable time per day | Minutes per month | At promotional rate | At listed regular rate |
| --- | ---: | ---: | ---: |
| 2 minutes | 60 | $2.10 | $4.20 |
| 5 minutes | 150 | $5.25 | $10.50 |
| 10 minutes | 300 | $10.50 | $21.00 |
| 15 minutes | 450 | $15.75 | $31.50 |
| 30 minutes | 900 | $31.50 | $63.00 |
| 60 minutes | 1,800 | $63.00 | $126.00 |

For example, twenty 30-second calls per day total 10 minutes/day: about **$10.50/month** at the promotional rate, before any extra connected time. Two people each using 10 minutes/day double that to **$21/month**. Simultaneous calls add together.

Use your own billable duration in this formula:

```text
estimated monthly cost = total billable minutes per day × days × USD rate per minute
```

## Quiet time and ending a conversation

Treat the **whole connected cloud session** as potentially billable when budgeting, including thinking, reply playback and silence. The public Live3 pricing page does not specify a billing increment or a precise silence rule; these examples do not assume a free idle period or import the separate ASR product's rounding rules. Your Fish usage records are authoritative.

- Waiting for the Windows wake phrase is local: it does not itself open a Fish session.
- During a connected call, muting, push-to-talk release or silence does **not** end that call. Use **End** or a supported ending phrase.
- The Windows/dashboard default timeout ends a call after 30 seconds of inactivity. It pauses while the assistant thinks or speaks; this is not a 30-second maximum session duration.
- Stock satellites keep a cloud session for follow-up context. Their bridge expires it after five minutes without a turn, checked every 30 seconds. This differs from the Windows timeout; several minutes of connected time may follow one short request. An explicit ending phrase closes it sooner.

For illustration, if twenty calls each remain connected for an extra 30 seconds, that adds 10 minutes/day: **another $10.50 per 30-day month** at $0.035/minute. If a session stayed connected continuously for 24 hours/day, the same formula would be **$1,512/month** at that rate. These are budgeting scenarios, not measured billing results or app behavior guarantees.

## Other charges and what is not included

Fish lists premium language models at additional token-based prices and telephone calls at an additional $0.01/minute. This project uses web audio with its configured Live3 agent; it does not rent phone numbers or configure telephone calls. See [Fish's agent pricing](https://fish.audio/live3/) for current add-ons.

The stock satellite path also uses the speech-to-text provider already selected in its Home Assistant pipeline. That provider may charge separately. Local STT has no separate API fee, although your own hardware and electricity still cost money. A Home Assistant Cloud subscription, if used, is also separate.

Fish's consumer voice-generation subscriptions and standalone TTS/ASR prices are different products; do not substitute their included generation minutes for Live3 agent minutes. See [Fish's plan FAQ](https://fish.audio/plan/) and [API pricing documentation](https://docs.fish.audio/developer-guide/models-pricing/pricing-and-rate-limits). Promotional credits, taxes, currency conversion, account-specific terms and any provider billing minimums can change the amount you actually pay. Check Fish's balance and usage records, particularly after first testing the satellite bridge. The app's inactivity timer is not an account spending limit.

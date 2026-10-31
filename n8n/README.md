# n8n: Pakka's action layer (optional)

> Sarvam understands and speaks. Cognee remembers. Rules and guards decide. **n8n acts.** People handle hard cases.

n8n never chooses an action. Pakka sends it an action **after** the guard has approved it and only when it is actually delivered (a message held until 8 am is sent at 8 am, not before). Without n8n, Pakka writes the same event to a local outbox and the lender view shows **"Action sent (simulated)"**. The demo works the same either way.

## What Pakka sends

```json
{"action": "notify_shortfall", "event_id": "ev_…", "language": "hi", "lender_id": "demo_nbfc_a",
 "merchant_id": "m_55136de3d432", "requires_human": false, "scheduled_for": null, "template_id": "T_SHORTFALL"}
```

- **No** names, phone numbers, message text or amounts. `merchant_id` is a pseudonym. In production n8n would look up the contact details and the approved template by id; in the demo it only logs.
- Header `X-Pakka-Signature: sha256=<HMAC of the body with N8N_WEBHOOK_SECRET>` and `X-Pakka-Event-Id`. The body is compact JSON with sorted keys.
- 5 s timeout, one retry. On failure the event stays in the local outbox (`failed → fallback`), and anything that needs a person still goes into Pakka's people queue.
- Each `event_id` is sent once (idempotent).

## Run it

```bash
# 1. Start n8n (Node 20+). The Code node needs Node's crypto module:
NODE_FUNCTION_ALLOW_BUILTIN=crypto npx n8n          # Windows PowerShell: $env:NODE_FUNCTION_ALLOW_BUILTIN="crypto"; npx n8n
# 2. Open http://localhost:5678 → Workflows → Import from file → n8n/pakka_workflow.json
# 3. In the "Verify HMAC" node, set SECRET (same as N8N_WEBHOOK_SECRET) and PAKKA_URL (where Pakka runs)
# 4. Open the Webhook node, copy the URL. "Test URL" works while you press "Listen for test event";
#    "Production URL" works once the workflow is Active.
# 5. In Pakka's .env:
N8N_WEBHOOK_URL=http://localhost:5678/webhook/pakka
N8N_WEBHOOK_SECRET=pakka-demo-secret
# 6. Restart Pakka. The status strip on /merchant shows "n8n: live".
```

## The workflow

```
Webhook ─▶ Verify HMAC ─▶ Respond 200 ─▶ Switch on action
                                          ├─ send   ─▶ SMS / WhatsApp (DISABLED) + Log (simulated send)
                                          ├─ wait   ─▶ Wait until scheduled_for ─▶ Log (reminder due)
                                          ├─ people ─▶ Add to RM queue: signed HTTP POST back to Pakka /merchant/lender/queue
                                          └─ other  ─▶ Log
```

- **send:** shortfall notices, pay links, reminders and carry-forward confirmations. The SMS node is disabled: Pakka's own app card is the channel in the demo.
- **wait:** a reminder with a time; n8n waits until then.
- **people:** handoffs, callbacks and requests routed to the lender go to the relationship-manager queue, shown in Pakka's lender view as "From n8n".

## For the demo

Keep the n8n canvas open next to Pakka: each "Run the day" or reply in Pakka shows a new execution in n8n (Executions tab), and handoffs come back into the lender view's people queue.

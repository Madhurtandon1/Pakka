# Merchant UI test report

Run: 31 Oct 2026 12:15 · target: local app, offline (no LLM, no Sarvam key) · **30 / 30 scenarios passed**

| # | Scenario | Result | Notes |
|---|---|---|---|
| 01 | 1. Landing page → merchant demo link works | ✅ pass |  |
| 02 | 2. Consent: notice, independent toggles, hours limit, Not now, Allow + version | ✅ pass |  |
| 03 | 3. Sharma Kirana (steady): several days, no messages, offers allowed | ✅ pass |  |
| 04 | 4. Ramesh Chai (rain): neutral cue, lender figures, reminder in hours, cured with no offer | ✅ pass |  |
| 05 | 5. Every quick-reply button gives its documented action and an audit row · `already_paid-human_handoff-A person from Demo NBFC A` | ✅ pass |  |
| 05 | 5. Every quick-reply button gives its documented action and an audit row · `callback-schedule_callback-will call you` | ✅ pass |  |
| 05 | 5. Every quick-reply button gives its documented action and an audit row · `lower_deduction-route_lower_deduction_request-has been sent to Demo NBFC A` | ✅ pass |  |
| 05 | 5. Every quick-reply button gives its documented action and an audit row · `pay_later-schedule_reminder-remind you` | ✅ pass |  |
| 05 | 5. Every quick-reply button gives its documented action and an audit row · `pay_today-send_pay_link-Pay via UPI` | ✅ pass |  |
| 05 | 5. Every quick-reply button gives its documented action and an audit row · `reschedule-route_reschedule_request-has been sent to Demo NBFC A` | ✅ pass |  |
| 06 | 6. Pay choice: two buttons when total due > today's gap, one when equal | ✅ pass |  |
| 07 | 7. Gupta General Store at 21:30: deferred, delivered next morning | ✅ pass |  |
| 08 | 8. Noor Tailors: early warning, hardship → person, contact stops, offers greyed | ✅ pass |  |
| 09 | 9. City Mobile Repair: "I already paid" → person; out-of-scope request → person | ✅ pass |  |
| 10 | 10. Cadence: every other day during a long shortfall, then a person | ✅ pass | Cadence: the person takes over on the 4th proactive contact (days 15, 17, 19 messaged; day 21 → person). The feature doc and README say "the third attempt goes to a person"; the code hands off after three attempts. The wording should say "after three messages". A worsening overdue stage (SMA-0 → SMA-1) can't be reached in the 30-day demo; it is covered by the unit tests.; The audit chip for that handover reads "Third try, so a person takes over" although it is the 4th contact. |
| 11 | 11. Withdraw consent: one tap, contact stops, distress still reaches a person | ✅ pass |  |
| 12 | 12. Never consented: a hardship reply still reaches a person | ✅ pass |  |
| 13 | 13. Language toggle: notice, card and buttons in Hindi, no untranslated English | ✅ pass |  |
| 14 | 14. "Show technical details" shows and hides codes | ✅ pass |  |
| 15 | 15. Lender view: ledger stages, requests, audit chips, tiles with 0 rules broken | ✅ pass |  |
| 16 | 16. Guided tour runs to the end without errors | ✅ pass |  |
| 17 | 17. Reset returns to a clean state | ✅ pass |  |
| 18 | 18. Speaker: Soundbox plays only the neutral cue; Listen reads the card; other text refused | ✅ pass |  |
| 19a | 19. Mic: transcript goes to the reply box, is not sent until Send; language follows toggle | ✅ pass |  |
| 19b | 19. Mic: browser without speech recognition → clear message | ✅ pass |  |
| 19c | 19. Mic: permission denied → clear message | ✅ pass |  |
| 20 | 20. Mobile viewport 390×844: no sideways overflow, buttons usable | ✅ pass |  |
| 21 | 21. Verma Fruit Cart: "Can't pay today" ×3 → carry-forward explained twice, then a callback is booked | ✅ pass |  |
| 22a | 22. Partners offline: status strip, simulated actions, people queue, memory and recall lines | ✅ pass |  |
| 22b | 22. Sarvam speech-to-text path: recorded audio → transcript in the box, not sent until Send | ✅ pass |  |

## Console errors

- None (apart from the expected ones below).
- Expected offline: 39 × "503" from the voice endpoints (no Sarvam key, so the page uses the browser's voice).

## Failed network requests

- None unexpected.
- Expected offline: 39 × 503 from `/speak` or `/soundbox/speak` (fallback to the browser's voice).

## Bugs found and fixed

- Mic sent the voice transcript straight away; now it goes into the reply box to check, edit and send.
- No message when the browser has no speech recognition or the microphone is blocked; both now explain what to do.
- After "Not now", the permission request came back on every refresh; "Not now" is now remembered for that shop.
- A shop owner without permission had nowhere to type, so a distress reply couldn't reach a person from the page; the permission screen now has a "Need help?" box (alerts stay off).
- Mobile (390 px): the page was 275 px wider than the screen; the header controls and phone now shrink.
- Hindi mode left English on the phone: header line, dates ("10 Oct", also inside the Hindi message), contact hours ("8 am–7 pm"), the reply-reader line and the permission title; all now in Hindi.
- The consent version was only visible with technical details on; it now shows after Allow and on the phone.
- Added a "Listen" button on the app card (the owner's own phone; the Soundbox still only plays the neutral cue).

## Unclear or inconsistent UI text

- Cadence: the person takes over on the 4th proactive contact (days 15, 17, 19 messaged; day 21 → person). The feature doc and README say "the third attempt goes to a person"; the code hands off after three attempts. The wording should say "after three messages". A worsening overdue stage (SMA-0 → SMA-1) can't be reached in the 30-day demo; it is covered by the unit tests.
- The audit chip for that handover reads "Third try, so a person takes over" although it is the 4th contact.

## Screenshots (59)

Saved in `e2e_report/`:

- 01_landing_link_01_landing.png
- 01_landing_link_02_merchant_page.png
- 02_consent_screen_01_notice.png
- 02_consent_screen_02_toggles_and_hours.png
- 02_consent_screen_03_not_now_no_contact.png
- 02_consent_screen_04_allowed.png
- 03_kirana_steady_01_five_quiet_days.png
- 03_kirana_steady_02_offers_allowed.png
- 04_chai_rain_01_shortfall_card_and_cue.png
- 04_chai_rain_02_pay_tomorrow_reminder.png
- 04_chai_rain_03_typed_kal_de_dunga.png
- 04_chai_rain_04_cured_no_offer.png
- 05_quick_replies[pay_today-send_pay_link-Pay via UPI]_01_pay_today.png
- 05_quick_replies[pay_later-schedule_reminder-remind you]_01_pay_later.png
- 05_quick_replies[lower_deduction-route_lower_deduction_request-has been sent to Demo NBFC A]_01_lower_deduction.png
- 05_quick_replies[reschedule-route_reschedule_request-has been sent to Demo NBFC A]_01_reschedule.png
- 05_quick_replies[callback-schedule_callback-will call you]_01_callback.png
- 05_quick_replies[already_paid-human_handoff-A person from Demo NBFC A]_01_already_paid.png
- 06_pay_choice_01_two_links.png
- 06_pay_choice_02_one_link.png
- 07_late_night_01_deferred.png
- 07_late_night_02_delivered_8am.png
- 08_tailor_illness_01_early_warning.png
- 08_tailor_illness_02_handoff.png
- 08_tailor_illness_03_contact_stopped.png
- 08_tailor_illness_04_offers_blocked.png
- 09_mobile_dispute_01_already_paid.png
- 09_mobile_dispute_02_out_of_scope.png
- 10_cadence_01_cadence.png
- 11_withdraw_01_withdrawn.png
- 11_withdraw_02_distress_after_withdraw.png
- 12_distress_without_consent_01_handoff_without_consent.png
- 12_distress_without_consent_02_non_distress_without_consent.png
- 13_hindi_01_hindi_notice.png
- 13_hindi_02_hindi_card.png
- 13_hindi_03_back_to_english.png
- 14_technical_details_01_tech_on.png
- 14_technical_details_02_tech_off.png
- 15_lender_view_01_lender_view.png
- 16_tour_01_tour_end.png
- 17_reset_01_clean.png
- 18_speaker_01_cue_played.png
- 18_speaker_02_listen_card.png
- 19a_mic_transcript_01_transcript_in_box.png
- 19a_mic_transcript_02_sent_after_tap.png
- 19b_mic_unsupported_01_unsupported.png
- 19c_mic_denied_01_denied.png
- 20_mobile_01_mobile_consent.png
- 20_mobile_02_mobile_card.png
- 21_fruit_cart_cant_pay_today_01_reason_chips.png
- 21_fruit_cart_cant_pay_today_02_day5_carry_forward.png
- 21_fruit_cart_cant_pay_today_03_day6_voice_and_stress_flag.png
- 21_fruit_cart_cant_pay_today_04_day7_callback_offer.png
- 21_fruit_cart_cant_pay_today_05_callback_booked_lender_view.png
- 22a_partners_offline_01_recall_ramesh.png
- 22a_partners_offline_02_actions_queue_memory.png
- 22a_partners_offline_03_memory_deleted_on_withdraw.png
- 22a_partners_offline_04_recall_city_mobile.png
- 22b_sarvam_voice_path_01_sarvam_transcript.png

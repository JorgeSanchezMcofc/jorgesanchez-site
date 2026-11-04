# Energy Check-in ("What fills your bucket?")

A 15-minute mental wellness check-in. People join on their phones with a room code, make 21 this-or-that picks (7 dimensions, 3 pairs each, left/right order randomized per person), get a private profile with "do more of" and "watch your energy around" reminders, and can email it to themselves. The big screen only shows anonymous group averages.

- Participant link: https://jorgesanchez.me/energycheck/ (also energycheck.jorgesanchez.me)
- Host screen: https://jorgesanchez.me/energycheck/#host

Without any setup it runs in **demo mode**: it works, but only between tabs in the same browser. Do steps 2 and 3 before the session.

## 1. Put it on GitHub Pages
1. New repo (for example `energy-checkin`), upload `index.html`.
2. Settings > Pages > Source: `main` branch, `/ (root)`. Save.
3. Wait about a minute and open the URL it gives you.

## 2. Firebase (live room sync, free)
1. Go to console.firebase.google.com > Add project (Analytics off is fine).
2. Build > Realtime Database > Create database > start in **test mode**.
3. Project settings (gear) > Your apps > Web `</>` > register. Copy `apiKey`, `authDomain`, `databaseURL`, `projectId`.
4. Paste them into the `CONFIG.firebase` block at the top of the `<script>` in `index.html`.
5. Rules (Realtime Database > Rules), so only rooms are writable:
```json
{ "rules": { "rooms": { "$code": { ".read": true, ".write": true } }, ".read": false, ".write": false } }
```
What gets stored: first name + the 1 to 5 scores. Emails are never stored. Delete the `rooms` node after the session if you want a clean slate.

## 3. EmailJS (sends the report, free up to 200/month)
1. emailjs.com > sign up > Email Services > connect your Gmail or Outlook. Copy the **Service ID**.
2. Email Templates > Create:
   - To Email: `{{to_email}}`
   - Subject: `Your energy check-in: {{profile}}`
   - Content (switch the editor to code view): `{{{report_html}}}`
   Copy the **Template ID**.
3. Account > General: copy the **Public Key**.
4. Paste all three into `CONFIG.emailjs`.

If EmailJS isn't set up, the button opens the person's own mail app with the report pre-filled instead.

## 15-minute run of show
| Min | What happens |
|---|---|
| 0:00 to 2:00 | Open `energycheck.jorgesanchez.me/host` on the projector. Frame it: "No right answers. Some of us refill alone, some with people." Everyone scans the QR. |
| 2:00 to 6:00 | Phones: 21 this-or-that picks, then "last week, how much did you get of each?" for their top 3, then "what drained you most this month?" (up to 2). The bucket fills as people finish. |
| 6:00 to 7:00 | People read their results, including their gap. |
| 7:00 to 10:00 | Click **Reveal results**. **Bubbles** (what recharges us), **Last week** (% who got little or none of their #1 recharge), **Drains** (what's draining us). Discuss. |
| 10:00 to 13:00 | Click **Tips**. Every phone now asks for one thing that works for them. Tips pop onto the wall with no names. Click any tip to hide it. |
| 13:00 to 15:00 | Everyone emails themselves their reminders. The email includes their gap, their tip, and tips from colleagues who recharge the same way. Close: "Pick one and try it before next Friday." |

**All picks** shows every this-or-that split if you want it.

Tip: hit **Start a new room** before the real session so test answers don't show up.

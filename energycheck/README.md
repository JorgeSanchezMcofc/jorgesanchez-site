# Energy Check-in ("What fills your bucket?")

A 15-minute mental wellness check-in. People join on their phones with a room code, rate 12 energy sources from 1 (drains me) to 5 (fills me up), get a private profile with "do more of" and "watch your energy around" reminders, and can email it to themselves. The big screen only shows anonymous group averages.

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
| 0:00 to 2:00 | Open `#host` on the projector. Frame it: "No right answers. Some of us refill alone, some with people. Let's see what fills our buckets." Everyone scans the QR. |
| 2:00 to 6:00 | Everyone answers the 12 items (about 3 min). Names turn green as they finish. |
| 6:00 to 7:00 | People read their own profile and reminders on their phone. |
| 7:00 to 10:00 | Click **Reveal results**. Read the room: top 3, bottom 3, and the Inner/Social/Balanced split. |
| 10:00 to 13:00 | Pairs: "What's one thing on your 'do more' list you've been skipping?" |
| 13:00 to 15:00 | Everyone emails themselves the reminders. Close: "Pick one and try it before next Friday." |

Tip: hit **New room** before the real session so test answers don't show up.

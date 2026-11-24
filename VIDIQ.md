# vidIQ research log (Gravity Candy)

vidIQ account: jellali.hamzaa@gmail.com (free plan: 150 credits / month, renews ~22nd of each month).
Every research call costs 5 credits; `vidiq_balance`, `vidiq_user_channels`, `vidiq_credit_usage_list`
and `vidiq_connect_youtube_channel` are free. The daily run uses vidIQ to choose the video while credits
remain, then falls back to the queue in `vidiq_plan.json` (see PLAYBOOK step 1).

## 2026-11-24: first research pass (30 credits)

Calls: outliers (Shorts, "satisfying bouncing ball physics simulation inside a circle", 3 months),
trending Shorts ("ball bouncing physics simulation satisfying", since 1 Oct, by recent VPH),
outliers (Shorts, "guess the christmas song bouncing ball simulation"), 3 title scores.

What is breaking out in our exact niche (2D ball-in-a-circle sims, last 3 months):
- **Guess the song** is the strongest repeatable format. Bouncy Physics (10.8K subs): "These Bounces Play a
  Famous Song. Can You Name It?" 829K; "Can You Name the Song Before the Last Ball Breaks?" 452K with 296
  comments; "Watch the Bounces Turn Into a Melody. Can You Name It?" 410K. bouncyball: "Which song is the
  bouncing balls playing?" 805K. Christmas marble music also works ("Jingle Bells on a Marble Xylophone" 93K
  at 49x; "We Wish You A Merry Christmas Marble Music" 222K).
- **Every bounce = 5% faster**: "Every bounce is 5% faster: the gaps add up to 49 seconds" 4.1M (2072x). Our `speed` kind.
- **Every bounce multiplies / splits**: "Everytime the ball bounces, it multiplies - Circle" 933K;
  "1 Ball Becomes 10,000" 136K in a day; "Every Ball Splits in Two 2 -> 2048" 43K. Our `multiply` kind.
- **Every bounce = more lines**: "1 ball vs 1,000,000 lines, every bounce = 10x more" 714K (115x). Our `lines` kind.
- **Break through / destroy**: "Will the ball break through the wood? Spiral" 11.3M (2327x); "Can One Ball Break
  Every Floor?" 573K; hydraulic press 3M. No engine kind yet (idea: rings with hit points instead of gaps).
- **Who wins battles**: "2 Balls vs 2,000,000 Balls - Who Wins?" 77K in a day from a 40-sub channel. Closest: `race`.

Title scores (vidiq_score_title, Shorts):
- "Every Bounce = Bigger Ball... Can You Guess the Christmas Song? 🎄 #satisfying #shorts" → 98
- "Can You Name the Christmas Song Before the Ball Fills the Circle? 🎄 #satisfying #shorts" → 98
- "Every Bounce Draws a Line (Deck the Halls) #satisfying #shorts" (our current template) → 91

Our own Shorts so far (Studio, 24 Nov): grow + Jingle Bells 8.8K (best), multiply 2.7K–3.1K, escape 1.2K,
lines + Merry Christmas 1.1K, race and speed too new to judge.

Decision: until Christmas, alternate **guess-the-Christmas-song** Shorts (engine `--guess --song ...`, which hides
the song name and reveals it at the end) with the proven non-music kinds (multiply, speed, lines, escape, race).
The ordered list is in `vidiq_plan.json`.

Ideas that need new engine kinds (not built yet): break-through rings with hit points; every ball splits in two
up to 2048; fill a shape; "1 ball vs N balls" battle.

## 2026-11-24 (evening): Gravity Candy connected to vidIQ (25 credits)

vidIQ connector now signed in as pondokarfouli456@gmail.com, which has Gravity Candy (UC6jSQGEwcejJGjanTUUb-rw)
connected. Free plan: 150 credits/month, renews 24 Dec. (The old account jellali.hamzaa@gmail.com only had "upfreelance".)

- `vidiq_youtube_channel_audit` (10 credits): YouTube Analytics had not reported 20–23 Nov yet, so private analytics
  (retention, traffic sources) are empty for our new Shorts. `vidiq_channel_analytics` for 20–24 Nov returned no rows
  (10 credits). Until Analytics catches up (2–3 days lag), use `vidiq_channel_videos` (public counts) instead.
- `vidiq_channel_videos` Shorts (5 credits), counts at ~19:10 UTC 24 Nov:

| Short | kind | views | likes | VPH (lifetime) |
| --- | --- | --- | --- | --- |
| hpKDHRWzvdo Every Bounce = Bigger Ball... Jingle Bells | grow + song | 9,486 | 49 | 190 |
| __jbfrSxFFs Every Bounce Adds a Ball... 300? | multiply | 3,230 | 20 | 66 |
| XxkVlSLgFVA Can One Ball Escape 10 Spinning Rings? | escape | 1,278 | 23 | 64 |
| tZOVAkL261c Every Bounce Draws a Line (Merry Christmas) | lines + song | 1,152 | 4 | 58 |
| DzAQHiiFgGs Which Color Escapes First? | race | 1,112 (in ~9 h) | 5 | 139 |
| XFSuuFAYvFE Every Bounce Makes It 5% Faster | speed | 76 (in 40 min) | 2 | — |

Reading: grow + Christmas song is clearly our best format; race took off fastest after it; escape has the best like
rate; lines with the song name in the title was the weakest. Queue reordered accordingly (grow-guess, race, multiply,
grow-guess, escape, lines-guess, speed, ...).

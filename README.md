[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/AfrizalSek/makefun-gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/AfrizalSek/makefun-gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

# GTA VI Twitch launch-day forecaster

Entry for `gta6-twitch-ccu-forecast-01` on make.fun: forecast how many people
watch Grand Theft Auto VI live on Twitch in each hour (2–24) of its release
day, 19 November 2026, as five quantiles per hour. Score is mean pinball
loss on the log scale.

## Method

Size-weighted launch-curve (kernel) over the case's own comparables. Each
comparable is a past big launch with a full 24-hour UTC launch day. For a
target with hour-1 print `p1`, every comparable contributes its log-ratio
curve `ln(viewers(h) / viewers(0))`; the forecast median at hour `h` is the
similarity-weighted median of those curves (Gaussian kernel on
`ln(hour-1 size)`, bandwidth 0.5), and the spread is the similarity-weighted
standard deviation of the curves (x0.8). The median ratio is capped at 4x.
Only clean comparables are used (tier "comparable" in the unlock notes).
When hour 1 is already a real launch hour (`p1 >= 20000`), only
comparables whose own hour 1 was a real share (>= 5%) of their day peak
are kept. Standard library only, deterministic, < 1 s per case.

## Local validation

No ground truth for the practice cases ships in the kit (the server scores
them), so validation uses 37 leave-one-out pseudo-launches built from the
kit's own comparables, scored with the exact pinball formula from RULES.txt:

| pool | this entry | house baseline |
|---|---|---|
| underway + comparable tier (n=19) | 0.267 | 0.403 |
| big underway, p1 >= 50k (n=13) | 0.166 | 0.243 |
| median loss, underway pool | 0.140 | — |

The final is a huge clean rolling-midnight launch, the regime where this
model is strongest (per-launch losses 0.09–0.19 on comparable big launches).
The real practice score is only known after submitting; this entry is
submitted to read it, then iterated on evidence.

## Run

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

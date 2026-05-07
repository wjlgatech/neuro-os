# What is this?

**Founder Loop** is an app that helps you keep promises to yourself.

You know how you wake up planning to ship something today, and at 3pm
you find yourself watching YouTube, and you don't even remember
deciding to? This app is built around a simple idea: that's not a
willpower problem. It's a *plumbing* problem. The version of you
who's tired and tempted at 3pm is a different person than the
deliberate, rested version of you who set the goals at 9am. So the app
helps morning-you write a contract that afternoon-you is bound by — but
in a way that's kind, not punishing.

Here's the metaphor stack the whole thing runs on.

## The deal with tomorrow-you

Every morning you spend two minutes telling the app what matters today,
in plain English. Things like:

> *I want to ship the report. I want to call my sister. I want to do
> two solid blocks of work on the database thing.*

The app, talking back like a friendly assistant, asks the questions
that turn each of these into something concrete: *how will we know it's
done? Is it must-do or nice-to-have?* When you've finished, it shows
you the contract and you click **Sign**. You've now made a deal with
the version of you who'll exist later today.

## The score

The app keeps a score for you, called the **tank**. It's a number
between 0% and 100%. As you finish things on your contract, the tank
fills up. As you waste time on things you didn't sign up for, the tank
drains a little. You don't have to look at the score; the app shows it
to you in three places — a tiny number on your browser toolbar, a
gauge in your menu bar, and a bar on every new tab you open.

## The reward

Here's the part that makes this different from every other
productivity app: **entertainment is good, when it's earned.** When
your tank hits 90%, the app unlocks however much YouTube / Twitter /
gaming time you set aside for yourself that morning. Default is 60
minutes. The timer runs; when it runs out, the app gently checks in.

Below 90%, the app doesn't *block* anything. You can still go to
YouTube. But:

## When you're tempted, the app shows you what you actually want

This is the heart of the whole thing.

When you go to YouTube at 3pm and your tank is at 60%, the app pops up
a small window. Not a nag. A window that names what's actually
happening:

> *You're tired. YouTube simulates rest but doesn't deliver it. Real
> rest options: 20-minute nap (tank +5%), or switch to your lighter
> task for 25 minutes, or 10-minute walk outside.*

You can pick one of those, or you can click **Proceed anyway**. The
"proceed anyway" button is always there, and clicking it is fine — it
just gets logged, and the tank drains a bit faster than usual.

The app distinguishes six "underlying needs" that distraction is
usually a stand-in for:

| When the urge fires, the real thing you want is often… | …and the app suggests… |
|---|---|
| Rest (you're tired) | A 20-minute nap, or switch to the lighter task |
| Novelty (the work is grindy) | A 10-minute deep-read of something you bookmarked |
| Connection (you've been alone) | A 5-minute voice message to one of three people |
| Escape from a stuck problem | A 10-minute walk + voice memo to externalize it |
| Decision-fatigue | Pick one small thing for 25 min, defer the rest |
| Hunger / eye-strain (your body) | Eat first, then re-decide |

The app isn't always right. When it's wrong, you click "Proceed
anyway" and that gets recorded too. Over time, the app learns your
patterns and gets less wrong.

## The memory

At the end of each day, the app shows you a one-page summary: what
got done, what didn't, where the tank ended up, what diagnoses fired,
what you accepted, what you proceeded-anyway through. Then it asks if
you want to plan tomorrow.

That's it. That's the whole product.

---

## Why this rather than another habit-tracker?

Three things that aren't in habit-trackers:

1. **The deal is signed by yesterday-you, not enforced by some
   external thing.** It's not Instagram telling you you've used it too
   long. It's *you*, this morning, asking *you, this afternoon* to
   honor a thing you both agreed to.
2. **Distraction is treated as a misaimed real desire, not a moral
   failure.** The app's job is to help you find the real thing you
   want, not to suppress the surface-level want.
3. **You always retain agency.** Nothing is ever blocked outright. The
   app makes the cost visible, but the choice is always yours.

It's a system to help you become more honest with yourself, not a cage.

---

## What it doesn't do (yet)

- It doesn't watch your phone — for now it's a desktop app.
- It doesn't tell anyone else how you're doing — your data lives only
  on your own machine. Nothing leaves it.
- It doesn't track your sleep or HRV directly — those signals come
  from a separate tool called **workflowx**. If you have workflowx
  installed, the app finds it automatically and uses it; if you don't,
  the app still works (it just relies on you logging urges manually
  via the browser extension or `neuro-os loop urge`). See
  [how it works](./how-it-works.md#box-1--sensors-what-the-app-knows-about-your-day)
  for what gets read where.

If any of this sounds interesting, see [how to use it](./how-to-use-it.md).

# NYC Poster: one-time setup (about 30–40 minutes)

NYC Poster is our own small Instagram scheduler. It has no monthly limit; Instagram's own limit is 100 posts a day. It runs free, as a GitHub Action in `sheryiansai-ai/nyc-carousel-media`, every 5 minutes.

You do steps 1–4 yourself, because they need your logins. **Never paste the token into chat**; it goes only into GitHub's secret box (step 4).

## 1. Check the Instagram account (2 minutes)

In the Instagram app: Settings → Account type and tools. **@notyourcollege** must be a **Professional (Business)** account linked to the **NYC Facebook Page**. Metricool already posts for us, so this is almost certainly done.

## 2. Make a Meta app (10 minutes)

1. Open **developers.facebook.com** in Brave. Log in with the Facebook account that manages the NYC Page.
2. Click **My Apps → Create app**.
3. For the use case, pick **Other**. For the app type, pick **Business**.
4. Name it **NYC Poster** and create it. If it asks for a business portfolio, choose NYC's, or skip.
5. On the app dashboard, add the **Instagram** product. Choose the setup **with Facebook login**, not "Instagram login".

The app can stay in **Development** mode. You are its admin, so it can post to your own account without Meta's app review.

## 3. Get a token that never expires (10 minutes)

1. Open **developers.facebook.com/tools/explorer** (Graph API Explorer).
2. On the right, set **Meta App** to **NYC Poster**, then pick **Get User Access Token**.
3. Under **Permissions**, add only these four:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_show_list`
   - `pages_read_engagement`

   Add `business_management` only if, in step 6, the NYC Page doesn't show up. That happens when the Page sits inside a business portfolio.
4. Click **Generate Access Token**. In the pop-up, choose the **NYC Page** and **@notyourcollege**, then allow.
5. Make it long-lived:
   1. Open **developers.facebook.com/tools/debug/accesstoken**.
   2. Paste the token and click **Debug**.
   3. At the bottom, click **Extend Access Token** and copy the new token.
6. Back in Graph API Explorer:
   1. Paste that long-lived token into the **Access Token** box.
   2. In the query box, type `me/accounts?fields=name,access_token,instagram_business_account` and click **Submit**.
   3. In the result, find the NYC Page and copy two things:
      - its **`access_token`**: this Page token does not expire;
      - **`instagram_business_account` → `id`**: a long number.

## 4. Put both in GitHub (3 minutes)

1. Open **github.com/sheryiansai-ai/nyc-carousel-media → Settings → Secrets and variables → Actions → New repository secret**.
2. Add `IG_TOKEN` = the Page `access_token` from step 3.6.
3. Add `IG_USER_ID` = the `instagram_business_account` id.

Then tell Claude "done". Claude will then:
- run a **check** that reads your account name and today's posting quota (it posts nothing);
- show you the result;
- move the bots to NYC Poster after your OK.

## How posts get in

Every post is a small file in `queue/` in the media repo, with its time, type (carousel, image, story or reel), image links and caption. The Action publishes it when its time comes and moves it to `queue/done/` with the Instagram link. `STATUS.md` in the repo lists what's coming up, what went out and what failed.

**What Instagram doesn't allow through any tool** (Metricool can't do these either):
- the music sticker on stories;
- link stickers.

Add those by hand in the app when you want them.

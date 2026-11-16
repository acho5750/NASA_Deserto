# Put the map on Render.com

The map is a static site: everything it needs is in the `map/` folder (HTML, JavaScript data files,
images). There is no server code and no build step, so Render's free **Static Site** plan is enough.

## Steps (about 5 minutes)

1. Go to https://dashboard.render.com and sign up or log in with **GitHub**.
2. Click **New +** (top right), then **Static Site**.
3. Under "Connect a repository", pick **acho5750/NASA_Deserto**. If it isn't listed, click
   "Configure account" and give Render access to that repository.
4. Fill in the form:
   | Field | Value |
   |---|---|
   | Name | `deserto` (this becomes the address, e.g. `https://deserto.onrender.com`; if taken, Render adds letters) |
   | Branch | `main` |
   | Root Directory | leave empty |
   | Build Command | leave empty (if Render insists on one, type `echo ok`) |
   | Publish Directory | `map` |
5. Click **Create Static Site** (or **Deploy Static Site**). The first deploy takes a minute or two;
   the log ends with "Your site is live".
6. Open the `https://<name>.onrender.com` address shown at the top of the page in a **private
   browser window** and check that the map loads, the chapters switch, and Play works.

After this, every push to `main` redeploys the site automatically (Settings -> Build & Deploy ->
Auto-Deploy: Yes is the default).

## Optional

- **Custom domain:** Settings -> Custom Domains -> Add, then add the DNS record Render shows you.
- **Web filter:** the Space Apps guide suggests asking FortiGuard to classify a new website so
  judges' networks don't block it: fill in the "FortiGuard Web Filter Classification" form
  linked from the Space Apps submission guide (Category: education or web-based application;
  Company Name: N/A).

## Then

Send us the new address. It replaces the live map link under "Link to Final Project" in
`docs/submission.md`. The GitHub Pages address (https://acho5750.github.io/NASA_Deserto/) keeps
working too, so you can list both.

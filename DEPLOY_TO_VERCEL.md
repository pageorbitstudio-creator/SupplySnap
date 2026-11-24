# Put SupplySnap online with Vercel

Follow these steps in order. You will need a GitHub account, a Vercel account, and a PostgreSQL database. The app's database is where products, people, and reorder requests are saved.

## 1. Put the app files on GitHub

1. Open [GitHub](https://github.com) and sign in.
2. Click **New repository**. Name it `supplysnap`, choose **Private**, and create it.
3. On the empty repository page, click **Add file → Upload files**.
4. On your computer, open this project's `SupplySnap` folder. Upload its app files, including `app.py`, `requirements.txt`, `package.json`, `package-lock.json`, `neon.ts`, and the `static` and `templates` folders.
5. **Do not upload** the `instance` folder, `__pycache__` folder, `.venv` folder, or any `.env` file. `instance` contains your local SQLite database; Vercel will use the new hosted database instead.
6. Click **Commit changes** at the bottom of the GitHub page.

When you're done, `app.py`, `requirements.txt`, `.python-version`, `package.json`, `neon.ts`, `static`, and `templates` should be visible on the main page of the GitHub repository. They should not be inside another `SupplySnap` folder.

## 2. Make the online database

1. The Neon production database is already set up for this app. The Neon CLI saved its connection values in this project's `.env.local` file.
2. Open `.env.local` privately, copy the complete value after `DATABASE_URL=`, and keep it private. Do not upload this file to GitHub or paste the value into a source-code file.

## 3. Tell Vercel how to start the app

1. Open [Vercel](https://vercel.com) and sign in. Connect your GitHub account if Vercel asks.
2. Click **Add New → Project**, find `supplysnap`, and click **Import**.
3. The project root is the repository root. Leave **Root Directory** blank/default. The files should show `app.py` and `requirements.txt` there.
4. If Vercel asks for a framework, choose **Flask**. Leave the build command and output directory blank/default.
5. Before you click **Deploy**, add these four environment variables. For each one, choose the **Production** environment:

   | Name | What to enter |
   | --- | --- |
   | `DATABASE_URL` | The full value after `DATABASE_URL=` in `.env.local` |
   | `SECRET_KEY` | A new random secret. In Terminal/PowerShell, run `python -c "import secrets; print(secrets.token_urlsafe(48))"` and paste the result. If `python` is not recognized on Windows, try `py` instead. Keep this value private. |
   | `ADMIN_EMAIL` | Your email address; this will be your administrator login |
   | `ADMIN_PASSWORD` | A new, strong password for SupplySnap. Do not reuse your email or GitHub password. |

   To add each variable, type its name in **Key**, its value in **Value**, and click **Add**. Do not add quotes around the values.

6. Click **Deploy** and wait for Vercel to finish. It may take a few minutes.

## 4. Open your app

Vercel will show a website address ending in `vercel.app`. Click it and sign in with the `ADMIN_EMAIL` and `ADMIN_PASSWORD` you entered. The app creates its database tables automatically on first start.

## If Vercel shows an error

- **Missing environment variable:** Open your Vercel project, then **Settings → Environment Variables**. Check that all four names above are present in **Production**. Add any missing ones, then open **Deployments** and redeploy.
- **Database connection error:** In Neon, click **Connect** again and copy the whole connection string. Replace the Vercel `DATABASE_URL` value with it, save, and redeploy.
- **App cannot find a file:** On GitHub, check that `app.py`, `requirements.txt`, `static`, and `templates` are at the repository's top level, not inside a second `SupplySnap` folder.
- **Build failed:** In Vercel, open the failed deployment and click **Build Logs**. The last red error is the useful one. The app does not need a Node.js build command.

Every future change you commit to GitHub will trigger a new Vercel deployment. Keep the Neon connection string, `SECRET_KEY`, and administrator password private.

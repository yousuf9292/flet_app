# Flet + Supabase Task Manager (Web/Desktop/Mobile)

This is a minimal, working, **multi-platform** Flet app that uses **Supabase Auth** + a **single shared Supabase client**
(no duplicated clients across pages).

## 1) Setup

1. Create a Supabase project.
2. Enable Email/Password auth in Supabase.
3. Create tables (example):

### `profiles` table
- `id` (uuid, primary key)
- `email` (text)
- `full_name` (text)

### `tasks` table
- `id` (uuid, primary key)
- `owner` (uuid)  -- should match auth.uid()
- `title` (text)
- `description` (text)
- `subtasks` (jsonb)  -- optional
- `comments` (jsonb)  -- optional
- `assignee` (uuid, nullable) -- optional
- `updated_at` (timestamptz)

> Tip: start without RLS while testing, then add RLS policies.

## 2) Configure keys

Edit `config/supabase_config.json`:

```json
{
  "SUPABASE_URL": "https://YOURPROJECT.supabase.co",
  "SUPABASE_ANON_KEY": "YOUR_ANON_KEY"
}
```

## 3) Run

Create venv + install:

```bash
pip install -r requirements.txt
```

Run desktop (local window):
```bash
flet run main.py
```

Run web:
```bash
flet run main.py --web
```

## 4) Build for all platforms (Flet CLI)

Flet supports building for desktop, web, Android (APK/AAB), and iOS (IPA). See Flet docs: `flet build`. citeturn0search0turn0search7turn0search19

Examples:

### Web bundle
```bash
flet build web
```

### Windows / macOS / Linux
```bash
flet build windows
flet build macos
flet build linux
```

### Android
```bash
flet build apk
# or
flet build aab
```

### iOS
```bash
flet build ipa
```

> Build prerequisites differ by platform; follow Flet "Publish" docs. citeturn0search7turn0search19


## Added features in this version

- ✅ Edit task (title/description)
- ✅ Subtasks (add/toggle/delete) stored in `tasks.subtasks` (jsonb)
- ✅ Assign task (stores UUID in `tasks.assignee`) using `profiles` table
- ✅ Comments (add + view) stored in `tasks.comments` (jsonb)
- ✅ Attach PDF: uploads to Supabase Storage bucket `task-pdfs`, sets task `status='closed'` and stores `pdf_url`
  - Remove PDF: deletes from Storage, clears `pdf_url`, sets `status='open'`

### Required columns in `tasks`
- `status` (text) default `'open'`
- `pdf_url` (text, nullable)
- `assignee` (uuid, nullable)
- `subtasks` (jsonb) default `'[]'::jsonb`
- `comments` (jsonb) default `'[]'::jsonb`

### Required table `profiles`
- `id` (uuid primary key)
- `email` (text)
- `full_name` (text)

### Required Storage bucket
Create a bucket in Supabase Storage named: `task-pdfs`.

This demo assumes the bucket is **public** (so `get_public_url()` works). If you keep it private,
switch to signed URLs.

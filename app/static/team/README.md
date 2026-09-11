# Team photos

Placeholder images for the "Our team" section on `/about`. Replace these
files with real photos whenever you like -- the about page just does
`<img src="/static/team/{{ e.photo }}">`, so nothing else needs to change
as long as the filename stays the same.

| Person | File to replace |
|---|---|
| Alice Tan | `app/static/team/alice-tan.svg` |
| Priya Nair | `app/static/team/priya-nair.svg` |
| Marcus Webb | `app/static/team/marcus-webb.svg` |
| Dana Okafor | `app/static/team/dana-okafor.svg` |

**If you replace a placeholder with a `.jpg`/`.png` instead of an `.svg`**,
also update that person's `photo` value in `database/seed.py` (search for
`"alice-tan.svg"` etc.) to the new filename, then re-seed
(`python database/seed.py` or `scripts/reset_lab.sh`) so the database
points at the right file. The card image area is a fixed square
(`.team-card-photo`, see `app/static/style.css`) with `object-fit: cover`,
so any reasonably square photo will crop in cleanly.

# shop-lab (deployment build)

This is a stripped deployment artifact, not the source repository. It
contains exactly what's needed to build and run the lab on a target host,
and nothing else -- no `.git` history, no design docs, no instructor
material. Source, docs, and history live in the private instructor repo;
never `git clone` that repo directly onto a student-facing host.

## Bring the lab up

```bash
cp .env.example .env
docker compose build
docker compose up -d
scripts/health_check.sh
```

## Reset between attempts / cohorts

```bash
docker compose exec --user root app scripts/reset_lab.sh
```

## Hard reset (new cohort, rebuild from scratch)

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

If something looks wrong, redeploy from a fresh export off the instructor
repo rather than patching this checkout in place.

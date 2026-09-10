# shop-lab application container.
#
# Isolation note (see docs/architecture.md): this container is the entire
# "vulnerable host" for Stages 8-12 (code execution as appuser, local
# enumeration, privilege escalation to root). Root *inside this container*
# is a training-lab result, not access to the real EC2 host -- there is no
# volume, socket, or capability mapping that lets a compromised process here
# reach the Docker host. Do not add one.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        sudo \
        tar \
        curl \
        procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/shop

COPY requirements.txt /opt/shop/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /opt/shop

# Provision the deliberate local privilege-escalation misconfiguration and
# the appuser/shopops accounts. Idempotent -- reset_lab.sh re-runs this
# inside a running container to restore state without rebuilding the image.
# Creates appuser/shopops, and sets correct ownership on scripts/, flags/,
# uploads/, database/, and logs/. App source files stay root-owned but
# world-readable (the default from COPY), which is all appuser needs to run
# the app -- it must NOT own its own source tree.
RUN chmod +x /opt/shop/vulnerable/privilege_escalation/setup_privesc.sh \
    && /opt/shop/vulnerable/privilege_escalation/setup_privesc.sh

ENV APP_ENV=lab \
    LAB_MODE=true \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5000 \
    DATABASE_URL=database/shop_lab.db \
    UPLOAD_DIR=uploads/images \
    LOG_DIR=logs

RUN chmod +x /opt/shop/scripts/entrypoint.sh

EXPOSE 5000

USER appuser

ENTRYPOINT ["/opt/shop/scripts/entrypoint.sh"]
CMD ["python", "run.py"]

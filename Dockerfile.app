# shop-lab application container.
#
# Isolation note (see docs/architecture.md): this container is the entire
# "vulnerable host" for the code-execution and privilege-escalation stages
# (code execution as appuser via the catalog-sync upload path, local
# enumeration, and the strict two-hop appuser -> opsuser -> root
# escalation -- see docs/attack-timeline.md for exact stage numbers). This
# is a single, deterministic path throughout -- no alternate route or
# shortcut exists at any stage. Root *inside this container* is a
# training-lab result, not access to the real EC2 host -- there is no
# volume, socket, or capability mapping that lets a compromised process
# here reach the Docker host. Do not add one.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        sudo \
        tar \
        curl \
        procps \
        libcap2-bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/shop

COPY requirements.txt /opt/shop/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /opt/shop

# Provision the deliberate local privilege-escalation misconfiguration and
# the appuser/opsuser accounts (two-hop chain, no group membership
# involved in either hop -- see vulnerable/privilege_escalation/README.md).
# Idempotent -- reset_lab.sh re-runs this inside a running container to
# restore state without rebuilding the image. Creates appuser/opsuser, and
# sets correct ownership on scripts/, flags/, uploads/, database/, and
# logs/. App source files stay root-owned but world-readable (the default
# from COPY), which is all appuser needs to run the app -- it must NOT own
# its own source tree.
RUN chmod +x /opt/shop/vulnerable/privilege_escalation/setup_privesc.sh \
    && /opt/shop/vulnerable/privilege_escalation/setup_privesc.sh

ENV FLASK_HOST=0.0.0.0 \
    FLASK_PORT=80 \
    DATABASE_URL=database/shop_lab.db \
    UPLOAD_DIR=uploads/images \
    LOG_DIR=logs

RUN chmod +x /opt/shop/scripts/entrypoint.sh

# Let appuser (non-root -- see the isolation note above; the privesc lab
# needs the running app itself to NOT already be root) bind directly to
# port 80. Docker containers already retain CAP_NET_BIND_SERVICE in their
# default capability set (no cap_add here -- nothing beyond Docker's own
# non-privileged default); setcap on the interpreter is what lets a
# non-root process actually exercise that capability, without making the
# process -- or anything else -- root.
RUN setcap 'cap_net_bind_service=+ep' "$(readlink -f "$(command -v python3)")"

EXPOSE 80

USER appuser

ENTRYPOINT ["/opt/shop/scripts/entrypoint.sh"]
CMD ["python", "run.py"]

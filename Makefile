.PHONY: help uv-sync service-install deploy

help:
	@echo "Targets:"
	@echo "  make deploy        uv sync + install service to /etc + restart"
	@echo "  make uv-sync       Sync Python deps via uv"
	@echo "  make service-install Install panelo.service into /etc/systemd/system"
	@echo ""
	@echo "Direct system commands:"
	@echo "  sudo systemctl restart panelo"
	@echo "  systemctl status panelo --no-pager"
	@echo "  journalctl -u panelo -f"
	@echo "  sudo nginx -t && sudo systemctl reload nginx"

uv-sync:
	uv sync

service-install:
	bash deploy/install_systemd.sh

deploy: uv-sync service-install
	sudo systemctl restart panelo
	systemctl status panelo --no-pager



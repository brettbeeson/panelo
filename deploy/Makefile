install-nginx:
	sudo install -m 644 nginx-panelo.conf /etc/nginx/sites-available/panelo
	sudo ln -sf /etc/nginx/sites-available/panelo /etc/nginx/sites-enabled/panelo

restart-nginx:
	sudo nginx -t && sudo systemctl reload nginx
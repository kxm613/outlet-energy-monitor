#/bin/bash

cd ~/energy-monitor/Web/monitorsite/
./manage.py collectstatic
sudo supervisorctl restart uwsgi
sudo service nginx restart

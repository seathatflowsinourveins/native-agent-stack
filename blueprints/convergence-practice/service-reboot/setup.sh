#!/bin/sh
set -eu
# Runs only inside the newly created guest via cloud-init.
mount -o ro /dev/disk/by-label/REBOOT_INPUT /mnt
mkdir -p /opt/service-reboot /var/lib/service-reboot
cp /mnt/* /opt/service-reboot/
chmod 0755 /opt/service-reboot
chmod 0644 /opt/service-reboot/*
chmod 0755 /opt/service-reboot/dagu
# Retain the original boot's service journal across this orderly reboot.
install -d -m 2755 -o root -g systemd-journal /var/log/journal
install -d /etc/systemd/journald.conf.d
printf '[Journal]\nStorage=persistent\n' > /etc/systemd/journald.conf.d/native-reboot.conf
systemctl restart systemd-journald
journalctl --flush
install -d -o example -g example /home/example/.config/systemd/user/timers.target.wants
install -m 0644 /opt/service-reboot/native-reboot.service /home/example/.config/systemd/user/
install -m 0644 /opt/service-reboot/native-reboot.timer /home/example/.config/systemd/user/
ln -s ../native-reboot.timer /home/example/.config/systemd/user/timers.target.wants/native-reboot.timer
chown -R example:example /home/example/.config /var/lib/service-reboot
install -m 0644 /opt/service-reboot/native-reboot-observer.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now --no-block native-reboot-observer.service
# Enabling linger starts this new guest user's manager. The enabled timer is the
# only workload activation mechanism on this and subsequent boots.
loginctl enable-linger example

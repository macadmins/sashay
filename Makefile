USE_PKGBUILD=1
include /usr/local/share/luggage/luggage.make
TITLE=sashay
REVERSE_DOMAIN=com.github.macadmins
PAYLOAD=\
	pack-usr-local-bin-sashay.py\
	pack-Library-LaunchDaemons-com.github.macadmins.sashay-daily.plist\
	pack-Library-LaunchDaemons-com.github.macadmins.sashay-weekly.plist
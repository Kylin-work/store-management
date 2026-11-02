#!/bin/bash
set -e

echo "Importing MySQL timezone tables..."
mysql_tzinfo_to_sql /usr/share/zoneinfo | mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" mysql
echo "Timezone tables imported."

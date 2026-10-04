import pymysql

# Django >= 5.2 refuses to start unless the MySQLdb driver reports version
# 2.2.1 or newer. PyMySQL reports 1.4.6, so we declare the supported version
# before handing the module over as MySQLdb. mysqlclient cannot be used here
# because it needs pkg-config and the MySQL development headers to build.
pymysql.version_info = (2, 2, 1, "final", 0)
pymysql.install_as_MySQLdb()

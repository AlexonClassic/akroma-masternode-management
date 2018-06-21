#!/usr/bin/env sh

isValidUsername() {
    if echo $1 | grep -Eq '^[[:lower:]_][[:lower:][:digit:]_-]{2,15}$'; then
        return 1
    fi
    return 0 
}

VERSION='0.1.1'
MEMORY=false
REMOVE=false
SYSTEMD=false
RPCPORT=8545
RPCUSER=
RPCPASSWORD=
SUCCESS=0

for i in "$@"
do
case $i in
    -m|--memory)
    MEMORY=true
    break
    shift # past argument=value
    ;;
    -r|--remove)
    REMOVE=true
    break
    shift # past argument=value
    ;;
    -s|--systemd)
    SYSTEMD=true
    shift # past argument=value
    ;;
    -p=*|--rpcport=*)
    RPCPORT="${i#*=}"
    if ! $(echo $RPCPORT | grep -Eq '^[0-9]+$') ; then
        echo "error: Provided RPC Port is not a number" >&2; exit 1
    fi
    echo '-p or --rpcport option will only be used when -s or --systemd is provided'
    shift # past argument=value
    ;;
    --rpcuser=*)
    RPCUSER="${i#*=}"
    shift # past argument=value
    ;;
    --rpcpassword=*)
    RPCPASSWORD="${i#*=}"
    shift # past argument=value
    ;;
    -h|--help)
    echo '-r or --remove option will remove and reverse installation of the akroma masternode client'
    echo '-s or --systemd will create a systemd service for starting and stopping the masternode instance'
    echo '-p=port# or --rpcport=port# option to set specific port# for geth rpc to listen on (option will only be used if systemd service is created)'
    echo '--rpcuser=user# option to set specific rpc user defined within Akroma dashboard (option will only be used if systemd service is created)'
    echo '--rpcpassword=password# option to set specific rpc password defined within Akroma dashboard (option will only be used if systemd service is created)'
    echo '-u=user# or --user=user# option to set/create user to run geth (for default user "akroma" use only -u/--user)'
    exit 1
    ;;
    -u=*|--user=*)
    USERNAME="${i#*=}"
    CREATE_USER=true
    isValidUsername $USERNAME
    if [ "$?" -eq 0 ] ; then
        echo 'Please provide valid username.'
        exit 2
    fi
    shift # past argument with no value
    ;;
    -u|--user) #user default username
    CREATE_USER=true
    USERNAME="akroma"
    shift # past argument with no value
    ;;
    *)
          # unknown option
    ;;
esac
done

if [ "$REMOVE" = true ]; then
echo '=========================='
echo 'Removing masternode installation...'
echo '=========================='
    if [ -f /etc/systemd/system/masternode.service ]; then
        sudo systemctl stop masternode && sudo systemctl disable masternode && sudo rm /etc/systemd/system/masternode.service
    fi
    if [ -f /etc/systemd/system/akromanode.service ]; then
        sudo systemctl stop akromanode && sudo systemctl disable akromanode && sudo rm /etc/systemd/system/akromanode.service
    fi
    sudo rm -f /usr/sbin/geth
    exit 0
fi

if [ -z "$RPCUSER" ] || [ -z "$RPCPASSWORD" ]
then
    echo '--rpcuser and --rpcpassword must be defined.  You can obtain these from the Akroma dashboard for this MasterNode'
    exit 2
fi

if [ "$CREATE_USER" = true ] ; then
    echo '=========================='
    echo "User configuration."
    echo '=========================='

    grep -q "$USERNAME" /etc/passwd
    if [ $? -ne $SUCCESS ] ; then
        echo "Creating user $USERNAME."
        sudo adduser $USERNAME --gecos "" --disabled-password --system --group
    else
        echo "User $USERNAME found."
    fi
fi

echo '=========================='
echo 'Installing dependencies...'
echo '=========================='
# install dependencies appropriately
sudo apt-get update && sudo apt-get install curl unzip wget -y

echo '=========================='
echo 'Installing akroma node...'
echo '=========================='
# Download release zip for node
arch=$(uname -m) 
if [ "$arch" = 'x86_64' ]; then
    sudo apt-get install jemalloc -y
    wget https://github.com/akroma-project/akroma/releases/download/$VERSION/release.linux-amd64.$VERSION.zip
elif [ "$arch" = 'armv5l' ]; then
    wget https://github.com/akroma-project/akroma/releases/download/$VERSION/release.linux-arm-5.$VERSION.zip
elif [ "$arch" = 'armv6l' ]; then
    wget https://github.com/akroma-project/akroma/releases/download/$VERSION/release.linux-arm-6.$VERSION.zip
elif [ "$arch" = 'armv7l' ]; then
    wget https://github.com/akroma-project/akroma/releases/download/$VERSION/release.linux-arm-7.$VERSION.zip
elif [ "$arch" = 'armv8l' ]; then
    wget https://github.com/akroma-project/akroma/releases/download/$VERSION/release.linux-arm-8.$VERSION.zip
elif [ "$arch" = 'aarch64' ]; then
    wget https://github.com/akroma-project/akroma/releases/download/$VERSION/release.linux-arm-64.$VERSION.zip
else
    wget https://github.com/akroma-project/akroma/releases/download/$VERSION/release.linux-386.$VERSION.zip
fi

# Unzip release zip file
unzip -o release.linux-*$VERSION.zip

# Make `geth` executable
chmod +x geth

# Cleanup
rm release.linux-*$VERSION.zip

if [ "$SYSTEMD" = true ]; then
    if [ -f /etc/systemd/system/masternode.service ]; then
        sudo systemctl stop masternode && sudo systemctl disable masternode && sudo rm /etc/systemd/system/masternode.service
    fi
    if [ -f /etc/systemd/system/akromanode.service ]; then
        sudo systemctl stop akromanode && sudo systemctl disable akromanode && sudo rm /etc/systemd/system/akromanode.service
    fi
echo '=========================='
echo 'Configuring service...'
echo '=========================='

cat > /tmp/akromanode.service << EOL
[Unit]
Description=Akroma Client -- masternode service
After=network.target

[Service]
EOL

if [ "$CREATE_USER" = true ] ; then
    cat >> /tmp/akromanode.service << EOL
User=${USERNAME}
Group=${USERNAME}
EOL
fi

cat >> /tmp/akromanode.service << EOL
Type=simple
Restart=always
RestartSec=30s
EOL
if [ "$MEMORY" = true ] && [ "$arch" = 'x86_64' ]
then
    cat >> /tmp/akromanode.service << EOL
Environment="LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.1"
EOL
fi

cat >> /tmp/akromanode.service << EOL
ExecStart=/usr/sbin/geth --masternode --rpcport ${RPCPORT} --rpcuser ${RPCUSER} --rpcpassword ${RPCPASSWORD}

[Install]
WantedBy=default.target
EOL
        sudo \mv /tmp/akromanode.service /etc/systemd/system
        sudo \cp geth /usr/sbin/
        systemctl status akromanode --no-pager --full
else
    echo 'systemd service will not be created.'
fi

echo 'Done.'

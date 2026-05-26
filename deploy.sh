#!/bin/bash

# ===========================================
# ESG Mefali Deployment Script
# Deploiement sur VPS (cohabitation avec UAfricas et autres)
# ===========================================

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Repertoire du script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Configuration
REMOTE_USER="root"
REMOTE_HOST="161.97.92.63"
REMOTE_DIR="/opt/esg_mefali"
REPO_URL="https://github.com/angenor/esg_mefali_v3.git"
# Branche deployee (la "version actuelle" preferee). Surclassable : BRANCH=main ./deploy.sh deploy
BRANCH="${BRANCH:-048-fix-chatbot-application-flow}"
DOMAIN="esg.mefali.com"
ADMIN_EMAIL="admin@mefali.com"

# Ports locaux (sur 127.0.0.1 du VPS, pour reverse proxy existant)
FRONTEND_PORT="3010"
BACKEND_PORT="8010"
POSTGRES_PORT="5434"

echo -e "${GREEN}=== ESG Mefali Deployment ===${NC}"
echo -e "Serveur: ${BLUE}${REMOTE_USER}@${REMOTE_HOST}${NC}"
echo -e "Repertoire: ${BLUE}${REMOTE_DIR}${NC}"
echo -e "Domaine: ${BLUE}${DOMAIN}${NC}"

# ========================================
# Helpers SSH
# ========================================
ssh_cmd() {
    ssh -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" "$@"
}

scp_cmd() {
    scp -o StrictHostKeyChecking=no "$@"
}

ssh_heredoc() {
    ssh -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}"
}

# ========================================
# SETUP - Installation initiale
# ========================================
setup() {
    echo -e "${GREEN}[1/6] Verification de la connexion SSH...${NC}"
    ssh_cmd "echo 'Connexion SSH reussie !'"

    echo -e "${GREEN}[2/6] Verification de Docker et Git...${NC}"
    ssh_heredoc << 'ENDSSH'
        # Docker (deja installe par UAfricas normalement)
        if ! command -v docker &> /dev/null; then
            echo "Installation de Docker..."
            curl -fsSL https://get.docker.com | sh
            systemctl enable docker
            systemctl start docker
        fi

        if ! docker compose version &> /dev/null; then
            echo "Installation de Docker Compose plugin..."
            apt-get update
            apt-get install -y docker-compose-plugin
        fi

        apt-get update
        apt-get install -y git curl openssl

        echo "Docker: $(docker --version)"
        echo "Docker Compose: $(docker compose version)"
        echo "Git: $(git --version)"
ENDSSH

    echo -e "${GREEN}[3/6] Creation du repertoire projet...${NC}"
    ssh_cmd "mkdir -p ${REMOTE_DIR}"

    echo -e "${GREEN}[4/6] Clonage du repository...${NC}"
    ssh_heredoc << ENDSSH
        cd ${REMOTE_DIR}

        if [ ! -d ".git" ]; then
            echo "Clonage du repository (branche ${BRANCH})..."
            cd /opt
            rm -rf esg_mefali
            git clone -b ${BRANCH} ${REPO_URL} esg_mefali
        else
            echo "Repository deja present, mise a jour (branche ${BRANCH})..."
            git fetch origin
            git checkout ${BRANCH} 2>/dev/null || true
            git reset --hard origin/${BRANCH}
        fi
ENDSSH

    echo -e "${GREEN}[5/6] Upload de l'exemple de virtual host Nginx...${NC}"
    ssh_cmd "mkdir -p ${REMOTE_DIR}/nginx"
    scp_cmd "${SCRIPT_DIR}/nginx/esg-mefali-vhost.conf.example" \
        "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/nginx/"

    echo -e "${GREEN}[6/6] Generation des secrets et creation du .env...${NC}"
    ssh_heredoc << ENDSSH
        cd ${REMOTE_DIR}

        if [ -f ".env" ]; then
            echo "Fichier .env existant conserve."
        else
            # Generer des secrets securises
            SECRET_KEY=\$(openssl rand -hex 32)
            POSTGRES_PWD=\$(openssl rand -hex 16)

            cat > .env << ENVEOF
# ==========================================
# ESG Mefali - Production
# ==========================================

# --- PostgreSQL ---
POSTGRES_DB=esg_mefali
POSTGRES_USER=esg_mefali
POSTGRES_PASSWORD=\${POSTGRES_PWD}
POSTGRES_PORT=${POSTGRES_PORT}

# --- Ports locaux (reverse proxy externe) ---
FRONTEND_PORT=${FRONTEND_PORT}
BACKEND_PORT=${BACKEND_PORT}

# --- Securite JWT ---
SECRET_KEY=\${SECRET_KEY}
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
REFRESH_TOKEN_EXPIRE_DAYS=30

# --- OpenRouter (LLM) ---
# IMPORTANT : remplacer CHANGEZ_MOI par votre cle OpenRouter
OPENROUTER_API_KEY=CHANGEZ_MOI
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=anthropic/claude-sonnet-4.6

# --- Embeddings Voyage (F12 / mig. 043) ---
# REQUIS : sans cle, la memoire contextuelle (message_chunks) est desactivee.
# Schema en vector(1024) -> modele 1024 dims (voyage-3.5), PAS voyage-large-2.
VOYAGE_API_KEY=CHANGEZ_MOI
VOYAGE_MODEL=voyage-3.5

# --- Application ---
APP_VERSION=0.1.0
ENVEOF

            echo ""
            echo "Secrets generes et sauvegardes dans .env :"
            echo "  POSTGRES_PASSWORD: \${POSTGRES_PWD}"
            echo "  SECRET_KEY: \${SECRET_KEY}"
            echo ""
            echo -e "\033[1;33m/!\\ OPENROUTER_API_KEY doit etre configuree manuellement !\033[0m"
            echo "  Editer avec : nano ${REMOTE_DIR}/.env"
        fi
ENDSSH

    echo ""
    echo -e "${GREEN}=== Setup termine ! ===${NC}"
    echo ""
    echo -e "${YELLOW}Prochaines etapes :${NC}"
    echo "  1. Configurer OPENROUTER_API_KEY dans .env :"
    echo "       ./deploy.sh connect"
    echo "       nano .env"
    echo ""
    echo "  2. Deployer :"
    echo "       ./deploy.sh deploy"
    echo ""
    echo "  3. Configurer le reverse proxy (nginx UAfricas) :"
    echo "       Voir : ${REMOTE_DIR}/nginx/esg-mefali-vhost.conf.example"
    echo "       Puis : ./deploy.sh ssl"
}

# ========================================
# DEPLOY - Deploiement complet
# ========================================
deploy() {
    echo -e "${GREEN}[1/4] Pull du code depuis GitHub...${NC}"
    ssh_heredoc << ENDSSH
        cd ${REMOTE_DIR}
        git fetch origin
        git checkout ${BRANCH} 2>/dev/null || true
        git reset --hard origin/${BRANCH}
ENDSSH

    echo -e "${GREEN}[2/4] Upload du virtual host d'exemple...${NC}"
    scp_cmd "${SCRIPT_DIR}/nginx/esg-mefali-vhost.conf.example" \
        "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/nginx/"

    echo -e "${GREEN}[3/4] Build et demarrage des containers...${NC}"
    ssh_heredoc << ENDSSH
        cd ${REMOTE_DIR}

        if [ ! -f ".env" ]; then
            echo "ERREUR: Fichier .env introuvable !"
            echo "Executez d'abord: ./deploy.sh setup"
            exit 1
        fi

        if grep -q "OPENROUTER_API_KEY=CHANGEZ_MOI" .env; then
            echo ""
            echo -e "\033[1;33m/!\\ ATTENTION : OPENROUTER_API_KEY n'est pas configuree !\033[0m"
            echo "Le backend demarrera avec le graphe LangGraph desactive."
            echo "Editez .env pour corriger : nano ${REMOTE_DIR}/.env"
            echo ""
        fi

        docker compose -f docker-compose.prod.yml down || true
        docker compose -f docker-compose.prod.yml build
        docker compose -f docker-compose.prod.yml up -d
        docker image prune -f
ENDSSH

    echo -e "${GREEN}[4/4] Verification du deploiement...${NC}"
    ssh_heredoc << ENDSSH
        cd ${REMOTE_DIR}
        echo "Etat des containers :"
        docker compose -f docker-compose.prod.yml ps

        echo ""
        echo "Attente du demarrage (backend + migrations Alembic)..."
        sleep 25

        echo ""
        echo "Health checks locaux :"
        curl -sf http://127.0.0.1:${BACKEND_PORT}/api/health \
            && echo " - Backend OK (port ${BACKEND_PORT})" \
            || echo " - Backend pas encore pret (port ${BACKEND_PORT})"
        curl -sf http://127.0.0.1:${FRONTEND_PORT}/ > /dev/null \
            && echo " - Frontend OK (port ${FRONTEND_PORT})" \
            || echo " - Frontend pas encore pret (port ${FRONTEND_PORT})"
ENDSSH

    echo ""
    echo -e "${GREEN}=== Deploiement termine ! ===${NC}"
    echo -e "Services locaux :"
    echo "  - Backend  : http://127.0.0.1:${BACKEND_PORT}/api/health"
    echo "  - Frontend : http://127.0.0.1:${FRONTEND_PORT}/"
    echo ""
    echo -e "${YELLOW}Pour exposer publiquement via nginx UAfricas :${NC}"
    echo "  ./deploy.sh vhost-install   # installe le virtual host dans nginx UAfricas"
    echo "  ./deploy.sh ssl             # obtient le certificat Let's Encrypt"
}

# ========================================
# UPDATE - Mise a jour rapide
# ========================================
update() {
    echo -e "${GREEN}Mise a jour rapide...${NC}"
    ssh_heredoc << ENDSSH
        cd ${REMOTE_DIR}
        git pull origin ${BRANCH}

        docker compose -f docker-compose.prod.yml build
        docker compose -f docker-compose.prod.yml up -d

        echo ""
        echo "Etat des containers :"
        docker compose -f docker-compose.prod.yml ps
ENDSSH
    echo -e "${GREEN}Mise a jour terminee !${NC}"
}

# ========================================
# LOGS - Voir les logs
# ========================================
logs() {
    SERVICE="${2:-}"
    if [ -n "$SERVICE" ]; then
        ssh_cmd "cd ${REMOTE_DIR} && docker compose -f docker-compose.prod.yml logs -f --tail=100 ${SERVICE}"
    else
        ssh_cmd "cd ${REMOTE_DIR} && docker compose -f docker-compose.prod.yml logs -f --tail=100"
    fi
}

# ========================================
# RESTART - Redemarrer les services
# ========================================
restart() {
    SERVICE="${2:-}"
    if [ -n "$SERVICE" ]; then
        echo -e "${GREEN}Redemarrage de ${SERVICE}...${NC}"
        ssh_cmd "cd ${REMOTE_DIR} && docker compose -f docker-compose.prod.yml restart ${SERVICE}"
    else
        echo -e "${GREEN}Redemarrage de tous les services...${NC}"
        ssh_cmd "cd ${REMOTE_DIR} && docker compose -f docker-compose.prod.yml restart"
    fi
    echo -e "${GREEN}Redemarrage effectue !${NC}"
}

# ========================================
# STOP - Arreter les services
# ========================================
stop() {
    echo -e "${YELLOW}Arret de tous les services ESG Mefali...${NC}"
    ssh_cmd "cd ${REMOTE_DIR} && docker compose -f docker-compose.prod.yml down"
    echo -e "${GREEN}Services arretes.${NC}"
}

# ========================================
# STATUS - Etat des services
# ========================================
status() {
    ssh_heredoc << ENDSSH
        cd ${REMOTE_DIR}
        echo "=== Etat des containers ESG Mefali ==="
        docker compose -f docker-compose.prod.yml ps

        echo ""
        echo "=== Dernier commit Git ==="
        git log -1 --oneline

        echo ""
        echo "=== Espace disque ==="
        df -h / | tail -1

        echo ""
        echo "=== Memoire ==="
        free -h | head -2

        echo ""
        echo "=== Health checks (127.0.0.1) ==="
        curl -sf http://127.0.0.1:${BACKEND_PORT}/api/health \
            && echo " - Backend OK" || echo " - Backend KO"
        curl -sf http://127.0.0.1:${FRONTEND_PORT}/ > /dev/null \
            && echo " - Frontend OK" || echo " - Frontend KO"
ENDSSH
}

# ========================================
# VHOST-INSTALL - Installer le virtual host dans nginx UAfricas
# ========================================
vhost_install() {
    echo -e "${GREEN}Installation du virtual host ESG Mefali dans nginx UAfricas...${NC}"
    ssh_heredoc << ENDSSH
        UAFRICAS_DIR="/opt/uafricas"

        if [ ! -d "\${UAFRICAS_DIR}" ]; then
            echo "ERREUR : /opt/uafricas introuvable."
            echo "Le virtual host ESG Mefali suppose un nginx UAfricas operationnel."
            echo "Alternatives : configurer manuellement un reverse proxy."
            exit 1
        fi

        # Copier le vhost dans le dossier conf.d d'UAfricas (si existe)
        # Sinon, afficher les instructions manuelles
        if [ -d "\${UAFRICAS_DIR}/nginx/conf.d" ]; then
            cp ${REMOTE_DIR}/nginx/esg-mefali-vhost.conf.example \
               \${UAFRICAS_DIR}/nginx/conf.d/esg-mefali.conf
            echo "Virtual host copie dans \${UAFRICAS_DIR}/nginx/conf.d/esg-mefali.conf"
            echo ""
            echo "ATTENTION : verifier que nginx UAfricas inclut bien conf.d/*.conf"
            echo "  grep -r 'include.*conf.d' \${UAFRICAS_DIR}/nginx/"
        else
            echo "Pas de dossier conf.d detecte. Instructions manuelles :"
            echo ""
            echo "1. Editer \${UAFRICAS_DIR}/nginx/nginx.conf"
            echo "2. Dans le bloc http{}, inclure :"
            echo "     include /etc/nginx/conf.d/esg-mefali.conf;"
            echo "3. Dans docker-compose.prod.yml d'UAfricas, monter :"
            echo "     - ${REMOTE_DIR}/nginx/esg-mefali-vhost.conf.example:/etc/nginx/conf.d/esg-mefali.conf:ro"
            echo "4. Permettre a nginx UAfricas d'atteindre 127.0.0.1 du host :"
            echo "     ajouter network_mode: host OU extra_hosts: host-gateway"
            echo ""
            echo "Fichier a integrer : ${REMOTE_DIR}/nginx/esg-mefali-vhost.conf.example"
            exit 1
        fi

        echo ""
        echo "Prochaine etape : ./deploy.sh ssl"
ENDSSH
}

# ========================================
# SSL - Configurer Let's Encrypt
# ========================================
ssl() {
    DOMAIN_ARG="${2:-${DOMAIN}}"
    EMAIL_ARG="${3:-${ADMIN_EMAIL}}"

    echo -e "${GREEN}Configuration SSL pour ${DOMAIN_ARG} (email : ${EMAIL_ARG})...${NC}"
    ssh_heredoc << ENDSSH
        apt-get update
        apt-get install -y certbot

        # Arreter temporairement nginx UAfricas pour liberer le port 80
        UAFRICAS_NGINX="uafricas_nginx"
        docker stop \${UAFRICAS_NGINX} 2>/dev/null || echo "(nginx UAfricas non actif)"

        # Obtenir le certificat (un seul -d car c'est un sous-domaine)
        certbot certonly --standalone \
            -d ${DOMAIN_ARG} \
            --non-interactive --agree-tos --email ${EMAIL_ARG}

        # Copier les certificats dans le dossier ssl du nginx UAfricas
        UAFRICAS_SSL_DIR="/opt/uafricas/nginx/ssl/esg-mefali"
        mkdir -p \${UAFRICAS_SSL_DIR}
        cp /etc/letsencrypt/live/${DOMAIN_ARG}/fullchain.pem \${UAFRICAS_SSL_DIR}/
        cp /etc/letsencrypt/live/${DOMAIN_ARG}/privkey.pem \${UAFRICAS_SSL_DIR}/

        # Redemarrer nginx UAfricas
        docker start \${UAFRICAS_NGINX} 2>/dev/null || true

        # Renouvellement automatique
        (crontab -l 2>/dev/null | grep -v "esg-mefali" ; \
         echo "15 3 * * * certbot renew --quiet --pre-hook 'docker stop \${UAFRICAS_NGINX}' --post-hook 'cp /etc/letsencrypt/live/${DOMAIN_ARG}/fullchain.pem \${UAFRICAS_SSL_DIR}/ && cp /etc/letsencrypt/live/${DOMAIN_ARG}/privkey.pem \${UAFRICAS_SSL_DIR}/ && docker start \${UAFRICAS_NGINX}' # esg-mefali") | crontab -

        echo ""
        echo "Certificat SSL installe pour ${DOMAIN_ARG}"
        echo "Certificats copies dans : \${UAFRICAS_SSL_DIR}"
        echo ""
        echo "Redemarrer nginx UAfricas pour prendre en compte la nouvelle conf :"
        echo "  cd /opt/uafricas && docker compose -f docker-compose.prod.yml restart nginx"
ENDSSH
}

# ========================================
# BACKUP - Sauvegarder la base de donnees
# ========================================
backup() {
    BACKUP_DIR="${SCRIPT_DIR}/backups"
    mkdir -p "${BACKUP_DIR}"
    BACKUP_FILE="${BACKUP_DIR}/backup_esg_mefali_$(date +%Y%m%d_%H%M%S).sql"

    echo -e "${GREEN}Sauvegarde de la base de donnees ESG Mefali...${NC}"
    # shellcheck disable=SC2029
    ssh_cmd "docker exec esg_mefali_db pg_dump -U esg_mefali esg_mefali" > "${BACKUP_FILE}"
    echo -e "${GREEN}Sauvegarde enregistree : ${BACKUP_FILE}${NC}"
    echo "Taille : $(du -h "${BACKUP_FILE}" | cut -f1)"
}

# ========================================
# RESTORE - Restaurer une sauvegarde
# ========================================
restore() {
    BACKUP_FILE="${2:-}"
    if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
        echo -e "${RED}ERREUR : fichier de sauvegarde introuvable.${NC}"
        echo "Usage : $0 restore <chemin_backup.sql>"
        exit 1
    fi

    echo -e "${YELLOW}Restauration depuis ${BACKUP_FILE}...${NC}"
    echo -e "${RED}/!\\ Cette operation va ecraser la base actuelle !${NC}"
    read -r -p "Confirmer (oui/non) : " CONFIRM
    if [ "$CONFIRM" != "oui" ]; then
        echo "Annule."
        exit 0
    fi

    cat "${BACKUP_FILE}" | ssh_cmd "docker exec -i esg_mefali_db psql -U esg_mefali esg_mefali"
    echo -e "${GREEN}Restauration terminee.${NC}"
}

# ========================================
# CONNECT - Connexion SSH directe
# ========================================
connect() {
    echo -e "${GREEN}Connexion au serveur...${NC}"
    ssh -o StrictHostKeyChecking=no "${REMOTE_USER}@${REMOTE_HOST}" \
        -t "cd ${REMOTE_DIR} && bash"
}

# ========================================
# REBUILD - Rebuild complet sans cache
# ========================================
rebuild() {
    echo -e "${YELLOW}Rebuild complet sans cache...${NC}"
    ssh_heredoc << ENDSSH
        cd ${REMOTE_DIR}
        docker compose -f docker-compose.prod.yml down
        docker compose -f docker-compose.prod.yml build --no-cache
        docker compose -f docker-compose.prod.yml up -d
        docker image prune -f

        echo ""
        echo "Etat des containers :"
        docker compose -f docker-compose.prod.yml ps
ENDSSH
    echo -e "${GREEN}Rebuild termine !${NC}"
}

# ========================================
# SHELL - Ouvrir un shell dans un container
# ========================================
shell() {
    SERVICE="${2:-backend}"
    echo -e "${GREEN}Shell dans le container ${SERVICE}...${NC}"
    ssh -o StrictHostKeyChecking=no -t "${REMOTE_USER}@${REMOTE_HOST}" \
        "cd ${REMOTE_DIR} && docker compose -f docker-compose.prod.yml exec ${SERVICE} /bin/sh"
}

# ========================================
# MIGRATE - Appliquer les migrations Alembic manuellement
# ========================================
migrate() {
    echo -e "${GREEN}Application des migrations Alembic...${NC}"
    ssh_cmd "cd ${REMOTE_DIR} && docker compose -f docker-compose.prod.yml exec -T backend alembic upgrade head"
    echo -e "${GREEN}Migrations appliquees.${NC}"
}

# ========================================
# MENU PRINCIPAL
# ========================================
case "$1" in
    setup)         setup ;;
    deploy)        deploy ;;
    update)        update ;;
    logs)          logs "$@" ;;
    restart)       restart "$@" ;;
    stop)          stop ;;
    status)        status ;;
    ssl)           ssl "$@" ;;
    vhost-install) vhost_install ;;
    backup)        backup ;;
    restore)       restore "$@" ;;
    connect)       connect ;;
    rebuild)       rebuild ;;
    shell)         shell "$@" ;;
    migrate)       migrate ;;
    *)
        echo -e "${GREEN}ESG Mefali Deployment Script${NC}"
        echo ""
        echo "Usage: $0 {commande} [options]"
        echo ""
        echo -e "${BLUE}Installation :${NC}"
        echo "  setup              Installation initiale (Docker, clone, .env)"
        echo ""
        echo -e "${BLUE}Deploiement :${NC}"
        echo "  deploy             Deploiement complet (pull + build + up)"
        echo "  update             Mise a jour rapide (pull + build + up)"
        echo "  rebuild            Rebuild sans cache (en cas de probleme)"
        echo "  migrate            Appliquer les migrations Alembic"
        echo ""
        echo -e "${BLUE}Reverse proxy (nginx UAfricas) :${NC}"
        echo "  vhost-install      Installer le virtual host dans nginx UAfricas"
        echo "  ssl                Obtenir le certificat Let's Encrypt"
        echo ""
        echo -e "${BLUE}Gestion :${NC}"
        echo "  status             Etat des containers et ressources"
        echo "  logs [service]     Voir les logs (backend, frontend, postgres)"
        echo "  restart [service]  Redemarrer les services"
        echo "  stop               Arreter tous les services"
        echo "  shell [service]    Ouvrir un shell dans un container"
        echo "  connect            SSH direct vers le serveur"
        echo ""
        echo -e "${BLUE}Sauvegarde :${NC}"
        echo "  backup             Sauvegarder la base de donnees"
        echo "  restore <fichier>  Restaurer une sauvegarde"
        echo ""
        echo -e "${BLUE}Exemples :${NC}"
        echo "  $0 setup                              # Premiere installation"
        echo "  $0 deploy                             # Deployer"
        echo "  $0 logs backend                       # Logs du backend"
        echo "  $0 ssl esg.mefali.com                 # SSL pour un domaine"
        echo "  $0 restore backups/backup_xxx.sql     # Restaurer une sauvegarde"
        exit 1
        ;;
esac

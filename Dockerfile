# Build Nextcloud from a specific commit/tag/branch of the server repo
FROM php:8.2-apache

# ---- Build args to select repo + commit ----
ARG NEXTCLOUD_REPO=https://github.com/nextcloud/server.git
ARG GIT_REF=master

# ---- System deps for PHP extensions & tools ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    git unzip rsync nano less \
    libpng-dev libjpeg62-turbo-dev libfreetype6-dev \
    libzip-dev libxml2-dev libicu-dev libgmp-dev \
    libbz2-dev libexif-dev libwebp-dev \
    libmagickwand-dev \
    && rm -rf /var/lib/apt/lists/*

# ---- PHP extensions commonly required by Nextcloud ----
# gd with jpeg/webp/freetype support
RUN docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp \
 && docker-php-ext-install -j"$(nproc)" \
    gd \
    bcmath \
    bz2 \
    exif \
    intl \
    gmp \
    opcache \
    pcntl \
    pdo_mysql \
    zip \
    xml

# (Optional but recommended) Imagick extension via PECL
#RUN pecl install imagick && docker-php-ext-enable imagick || true

# ---- Apache modules ----
RUN a2enmod rewrite headers env dir mime setenvif

# ---- Tune PHP (basic, adjust as needed) ----
RUN { \
  echo "memory_limit=512M"; \
  echo "upload_max_filesize=512M"; \
  echo "post_max_size=512M"; \
  echo "max_execution_time=360"; \
  echo "output_buffering=0"; \
} > /usr/local/etc/php/conf.d/nextcloud.ini

# ---- Fetch Nextcloud source from Git and checkout specific ref ----
WORKDIR /usr/src
RUN git clone --recursive "$NEXTCLOUD_REPO" nextcloud 
RUN cd nextcloud \
 && git fetch --all --tags \
 && git checkout "$GIT_REF" \
 && git submodule update --init --recursive

# ---- (Optional) Composer install for source builds ----
# Official release tarballs include vendor/3rdparty; the git repo usually requires composer.
# If your chosen ref already contains vendor/3rdparty, this will do nothing or be quick.
# We install Composer locally and run install with --no-dev.
RUN php -r "copy('https://getcomposer.org/installer', 'composer-setup.php');" \
 && php composer-setup.php --install-dir=/usr/local/bin --filename=composer \
 && rm composer-setup.php \
 && cd /usr/src/nextcloud \
 && if [ -f composer.json ]; then composer install --no-dev -o || true; fi


RUN docker-php-ext-install -j"$(nproc)" mysqli 
RUN apt-get update && apt-get install -y --no-install-recommends util-linux && rm -rf /var/lib/apt/lists/*

# ---- Deploy to Apache docroot ----
# Keep code in image; persist only config, data, apps, themes via volumes in compose.
WORKDIR /var/www/html
RUN rm -rf /var/www/html/* \
 && rsync -a /usr/src/nextcloud/ /var/www/html/ \
 && chown -R www-data:www-data /var/www/html

# Ensure dirs exist in the image (helps first run)
RUN mkdir -p /var/www/html/config /var/www/html/data /var/www/html/custom_apps /var/www/html/themes \
 && chown -R www-data:www-data /var/www/html

# Healthcheck: try the front controller
HEALTHCHECK --interval=30s --timeout=10s --retries=10 \
  CMD php -r 'echo file_exists("/var/www/html/index.php") ? "OK" : "NO";' | grep -q OK || exit 1

RUN pecl install redis apcu \
 && docker-php-ext-enable redis apcu


COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

EXPOSE 80
CMD ["apache2-foreground"]

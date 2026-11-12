-- UniConnect AI schema snapshot 2026-11-09
-- Structure only, for an empty database or ERD import. Prefer Django migrations for app setup.
-- No INSERT, DROP, passwords or business records.
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;

CREATE TABLE `accounts_profile` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `role` varchar(20) COLLATE utf8mb4_bin NOT NULL,
  `expected_score` decimal(4,2) DEFAULT NULL,
  `target_combination` varchar(10) COLLATE utf8mb4_bin NOT NULL,
  `target_major` varchar(200) COLLATE utf8mb4_bin NOT NULL,
  `city` varchar(120) COLLATE utf8mb4_bin NOT NULL,
  `bio` varchar(300) COLLATE utf8mb4_bin NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `user_id` int NOT NULL,
  `avatar` varchar(100) COLLATE utf8mb4_bin NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  CONSTRAINT `accounts_profile_user_id_49a85d32_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `ai_chat_aichatmessage` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `role` varchar(20) COLLATE utf8mb4_bin NOT NULL,
  `content` longtext COLLATE utf8mb4_bin NOT NULL,
  `intent` varchar(50) COLLATE utf8mb4_bin NOT NULL,
  `payload` json NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `conversation_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ai_chat_aichatmessag_conversation_id_b7c58ead_fk_ai_chat_a` (`conversation_id`),
  CONSTRAINT `ai_chat_aichatmessag_conversation_id_b7c58ead_fk_ai_chat_a` FOREIGN KEY (`conversation_id`) REFERENCES `ai_chat_aichatsession` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `ai_chat_aichatsession` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `session_key` varchar(64) COLLATE utf8mb4_bin NOT NULL,
  `title` varchar(180) COLLATE utf8mb4_bin NOT NULL,
  `context` json NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `user_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ai_chat_aichatsession_user_id_6cf8b691_fk_auth_user_id` (`user_id`),
  KEY `ai_chat_aichatsession_session_key_022ced32` (`session_key`),
  CONSTRAINT `ai_chat_aichatsession_user_id_6cf8b691_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `auth_group` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(150) COLLATE utf8mb4_bin NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `auth_group_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `group_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `auth_permission` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_bin NOT NULL,
  `content_type_id` int NOT NULL,
  `codename` varchar(100) COLLATE utf8mb4_bin NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`),
  CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `auth_user` (
  `id` int NOT NULL AUTO_INCREMENT,
  `password` varchar(128) COLLATE utf8mb4_bin NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) COLLATE utf8mb4_bin NOT NULL,
  `first_name` varchar(150) COLLATE utf8mb4_bin NOT NULL,
  `last_name` varchar(150) COLLATE utf8mb4_bin NOT NULL,
  `email` varchar(254) COLLATE utf8mb4_bin NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `auth_user_groups` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `group_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_groups_user_id_group_id_94350c0c_uniq` (`user_id`,`group_id`),
  KEY `auth_user_groups_group_id_97559544_fk_auth_group_id` (`group_id`),
  CONSTRAINT `auth_user_groups_group_id_97559544_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
  CONSTRAINT `auth_user_groups_user_id_6a12ed8b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `auth_user_user_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_user_permissions_user_id_permission_id_14a6b632_uniq` (`user_id`,`permission_id`),
  KEY `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `career_careerassessment` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `framework` varchar(30) COLLATE utf8mb4_bin NOT NULL,
  `answers` json NOT NULL,
  `scores` json NOT NULL,
  `holland_code` varchar(6) COLLATE utf8mb4_bin NOT NULL,
  `suggested_majors` json NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `career_careerassessment_user_id_50420b7d_fk_auth_user_id` (`user_id`),
  CONSTRAINT `career_careerassessment_user_id_50420b7d_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `catalog_admissionrelease` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `title` varchar(160) COLLATE utf8mb4_bin NOT NULL,
  `rows` json NOT NULL,
  `status` varchar(12) COLLATE utf8mb4_bin NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `reviewed_at` datetime(6) DEFAULT NULL,
  `source_sha256` varchar(64) COLLATE utf8mb4_bin NOT NULL,
  `created_by_id` int DEFAULT NULL,
  `reviewed_by_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `catalog_admissionrelease_created_by_id_3167988a_fk_auth_user_id` (`created_by_id`),
  KEY `catalog_admissionrelease_reviewed_by_id_2d62fa7f_fk_auth_user_id` (`reviewed_by_id`),
  CONSTRAINT `catalog_admissionrelease_created_by_id_3167988a_fk_auth_user_id` FOREIGN KEY (`created_by_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `catalog_admissionrelease_reviewed_by_id_2d62fa7f_fk_auth_user_id` FOREIGN KEY (`reviewed_by_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `catalog_admissionreleaselock` (
  `id` smallint unsigned NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `catalog_admissionreleaselock_chk_1` CHECK ((`id` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `catalog_saveduniversity` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `university_key` varchar(220) COLLATE utf8mb4_bin NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_saved_university_per_user` (`user_id`,`university_key`),
  CONSTRAINT `catalog_saveduniversity_user_id_a696b7b8_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `config_requestbucket` (
  `key` varchar(64) COLLATE utf8mb4_bin NOT NULL,
  `count` int unsigned NOT NULL,
  `expires_at` datetime(6) NOT NULL,
  PRIMARY KEY (`key`),
  KEY `config_requestbucket_expires_at_f5c0cefb` (`expires_at`),
  CONSTRAINT `config_requestbucket_chk_1` CHECK ((`count` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `connections_userfollow` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `follower_id` int NOT NULL,
  `following_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_uniconnect_follow` (`follower_id`,`following_id`),
  KEY `connections_userfollow_following_id_44b00f1e_fk_auth_user_id` (`following_id`),
  CONSTRAINT `connections_userfollow_follower_id_21b32ece_fk_auth_user_id` FOREIGN KEY (`follower_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `connections_userfollow_following_id_44b00f1e_fk_auth_user_id` FOREIGN KEY (`following_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `prevent_uniconnect_self_follow` CHECK ((`follower_id` <> `following_id`))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `django_admin_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext COLLATE utf8mb4_bin,
  `object_repr` varchar(200) COLLATE utf8mb4_bin NOT NULL,
  `action_flag` smallint unsigned NOT NULL,
  `change_message` longtext COLLATE utf8mb4_bin NOT NULL,
  `content_type_id` int DEFAULT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `django_admin_log_content_type_id_c4bce8eb_fk_django_co` (`content_type_id`),
  KEY `django_admin_log_user_id_c564eba6_fk_auth_user_id` (`user_id`),
  CONSTRAINT `django_admin_log_content_type_id_c4bce8eb_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  CONSTRAINT `django_admin_log_user_id_c564eba6_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `django_admin_log_chk_1` CHECK ((`action_flag` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `django_content_type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) COLLATE utf8mb4_bin NOT NULL,
  `model` varchar(100) COLLATE utf8mb4_bin NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `django_migrations` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `app` varchar(255) COLLATE utf8mb4_bin NOT NULL,
  `name` varchar(255) COLLATE utf8mb4_bin NOT NULL,
  `applied` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `django_session` (
  `session_key` varchar(40) COLLATE utf8mb4_bin NOT NULL,
  `session_data` longtext COLLATE utf8mb4_bin NOT NULL,
  `expire_date` datetime(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `django_session_expire_date_a5c62663` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `social_comment` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `content` longtext COLLATE utf8mb4_bin NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `author_id` int NOT NULL,
  `post_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `social_comment_author_id_efe921df_fk_auth_user_id` (`author_id`),
  KEY `social_comment_post_id_c5f61de0_fk_social_post_id` (`post_id`),
  CONSTRAINT `social_comment_author_id_efe921df_fk_auth_user_id` FOREIGN KEY (`author_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `social_comment_post_id_c5f61de0_fk_social_post_id` FOREIGN KEY (`post_id`) REFERENCES `social_post` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `social_directmessage` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `content` longtext COLLATE utf8mb4_bin NOT NULL,
  `read` tinyint(1) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `recipient_id` int NOT NULL,
  `sender_id` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `social_directmessage_recipient_id_fa9d3a7f_fk_auth_user_id` (`recipient_id`),
  KEY `social_directmessage_sender_id_fa5c51ff_fk_auth_user_id` (`sender_id`),
  CONSTRAINT `social_directmessage_recipient_id_fa9d3a7f_fk_auth_user_id` FOREIGN KEY (`recipient_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `social_directmessage_sender_id_fa5c51ff_fk_auth_user_id` FOREIGN KEY (`sender_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `social_notification` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `kind` varchar(20) COLLATE utf8mb4_bin NOT NULL,
  `read` tinyint(1) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `actor_id` int NOT NULL,
  `post_id` bigint DEFAULT NULL,
  `recipient_id` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `social_notification_actor_id_78e4b611_fk_auth_user_id` (`actor_id`),
  KEY `social_notification_post_id_b9ab7062_fk_social_post_id` (`post_id`),
  KEY `social_notification_recipient_id_392d8c89_fk_auth_user_id` (`recipient_id`),
  CONSTRAINT `social_notification_actor_id_78e4b611_fk_auth_user_id` FOREIGN KEY (`actor_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `social_notification_post_id_b9ab7062_fk_social_post_id` FOREIGN KEY (`post_id`) REFERENCES `social_post` (`id`),
  CONSTRAINT `social_notification_recipient_id_392d8c89_fk_auth_user_id` FOREIGN KEY (`recipient_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `social_pollvote` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `option` smallint unsigned NOT NULL,
  `post_id` bigint NOT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `one_poll_vote_per_user` (`post_id`,`user_id`),
  KEY `social_pollvote_user_id_458719f1_fk_auth_user_id` (`user_id`),
  CONSTRAINT `social_pollvote_post_id_a960c11a_fk_social_post_id` FOREIGN KEY (`post_id`) REFERENCES `social_post` (`id`),
  CONSTRAINT `social_pollvote_user_id_458719f1_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `social_pollvote_chk_1` CHECK ((`option` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `social_post` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `content` longtext COLLATE utf8mb4_bin NOT NULL,
  `category` varchar(30) COLLATE utf8mb4_bin NOT NULL,
  `tag` varchar(80) COLLATE utf8mb4_bin NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `author_id` int NOT NULL,
  `poll_options` json NOT NULL DEFAULT (_utf8mb4'[]'),
  PRIMARY KEY (`id`),
  KEY `social_post_author_id_db6459ee_fk_auth_user_id` (`author_id`),
  CONSTRAINT `social_post_author_id_db6459ee_fk_auth_user_id` FOREIGN KEY (`author_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `social_postimage` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `image` varchar(100) COLLATE utf8mb4_bin NOT NULL,
  `post_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `social_postimage_post_id_9712fec4_fk_social_post_id` (`post_id`),
  CONSTRAINT `social_postimage_post_id_9712fec4_fk_social_post_id` FOREIGN KEY (`post_id`) REFERENCES `social_post` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `social_postlike` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `post_id` bigint NOT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_uniconnect_post_like` (`post_id`,`user_id`),
  KEY `social_postlike_user_id_5b69509e_fk_auth_user_id` (`user_id`),
  CONSTRAINT `social_postlike_post_id_2e49b122_fk_social_post_id` FOREIGN KEY (`post_id`) REFERENCES `social_post` (`id`),
  CONSTRAINT `social_postlike_user_id_5b69509e_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE `social_savedpost` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `post_id` bigint NOT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_uniconnect_saved_post` (`post_id`,`user_id`),
  KEY `social_savedpost_user_id_ecf5fc13_fk_auth_user_id` (`user_id`),
  CONSTRAINT `social_savedpost_post_id_9b499101_fk_social_post_id` FOREIGN KEY (`post_id`) REFERENCES `social_post` (`id`),
  CONSTRAINT `social_savedpost_user_id_ecf5fc13_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

SET FOREIGN_KEY_CHECKS=1;

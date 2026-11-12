-- Open this file in MySQL Workbench on 127.0.0.1:3306.
-- All statements below are read-only; no passwords are selected.
SHOW DATABASES LIKE 'uniconnect_ai';
USE uniconnect_ai;
SHOW TABLES;

SELECT id, username, email, is_staff, is_superuser
FROM auth_user
ORDER BY id
LIMIT 20;

SELECT id, author_id, content, category, created_at
FROM social_post
ORDER BY id DESC
LIMIT 20;

SELECT 'users' AS record_type, COUNT(*) AS total FROM auth_user
UNION ALL SELECT 'posts', COUNT(*) FROM social_post
UNION ALL SELECT 'comments', COUNT(*) FROM social_comment
UNION ALL SELECT 'ai_sessions', COUNT(*) FROM ai_chat_aichatsession;

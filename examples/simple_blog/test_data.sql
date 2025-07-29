-- Test data insertion script for simple_blog example
-- This script adds comprehensive test data to demonstrate the API capabilities

-- Clear existing data to ensure clean state
DELETE FROM post;
DELETE FROM author;

-- Reset sequences to start from 1
ALTER SEQUENCE author_id_seq RESTART WITH 1;
ALTER SEQUENCE post_id_seq RESTART WITH 1;

-- Insert Authors with diverse profiles
INSERT INTO author (name, email, bio, created_at) VALUES
    ('Alice Johnson', 'alice.johnson@techblog.com', 'Senior software engineer with 10+ years experience in Python and Django. Passionate about clean code and best practices.', '2023-01-15 10:30:00+00'),
    ('Bob Martinez', 'bob.martinez@devworld.com', 'Full-stack developer and tech enthusiast. Loves writing about web development, APIs, and modern JavaScript frameworks.', '2023-02-20 14:45:00+00'),
    ('Carol Chen', 'carol.chen@airesearch.org', 'AI researcher and data scientist. Enjoys sharing insights about machine learning, data analysis, and Python libraries.', '2023-03-10 09:15:00+00'),
    ('David Kumar', 'david.kumar@opensource.dev', 'Open source contributor and DevOps engineer. Writes about containerization, CI/CD, and infrastructure automation.', '2023-04-05 16:20:00+00'),
    ('Emma Thompson', 'emma.thompson@designcode.io', 'UI/UX designer who codes. Focuses on the intersection of design and development, accessibility, and user experience.', '2023-05-12 11:10:00+00'),
    ('Frank Wilson', 'frank.wilson@startuptech.com', 'Startup founder and tech blogger. Shares experiences about building products, team management, and entrepreneurship.', '2023-06-18 13:30:00+00'),
    ('Grace Liu', 'grace.liu@cloudnative.dev', 'Cloud architect and Kubernetes expert. Writes about cloud-native technologies, microservices, and scalable architectures.', '2023-07-22 08:45:00+00'),
    ('Henry Adams', 'henry.adams@cybersecurity.net', 'Cybersecurity specialist with focus on web application security, penetration testing, and secure coding practices.', '2023-08-14 15:55:00+00'),
    ('Isabel Rodriguez', 'isabel.rodriguez@mobiledev.com', 'Mobile app developer specializing in React Native and Flutter. Passionate about cross-platform development and UX.', '2023-09-08 12:25:00+00'),
    ('Jack Thompson', 'jack.thompson@gamedev.studio', 'Game developer and computer graphics enthusiast. Writes about game engines, graphics programming, and interactive media.', '2023-10-03 17:40:00+00');

-- Insert diverse blog posts with different statuses and dates
INSERT INTO post (title, slug, content, published_date, author_id, status, read_count) VALUES
    -- Alice's posts (Python/Django focus)
    ('Getting Started with Django REST Framework', 'getting-started-django-rest-framework', 'Django REST Framework (DRF) is a powerful toolkit for building Web APIs in Django. In this comprehensive guide, we''ll explore the fundamentals of DRF, from setting up your first API endpoint to implementing authentication and permissions. We''ll cover serializers, viewsets, and best practices for building scalable APIs.', '2023-01-20', 1, 'published', 1250),
    ('Advanced Django ORM Techniques', 'advanced-django-orm-techniques', 'The Django ORM is incredibly powerful, but many developers only scratch the surface. In this deep dive, we''ll explore advanced querying techniques, optimization strategies, and lesser-known features that can dramatically improve your application''s performance.', '2023-02-15', 1, 'published', 892),
    ('Building Scalable APIs with DRF', 'building-scalable-apis-drf', 'Scalability is crucial for modern web applications. This article covers architectural patterns, caching strategies, and optimization techniques for building APIs that can handle millions of requests. We''ll also discuss monitoring and performance measurement.', '2023-03-22', 1, 'published', 1456),
    ('Django Testing Best Practices', 'django-testing-best-practices', 'Comprehensive guide to testing Django applications, including unit tests, integration tests, and test-driven development practices.', '2023-04-18', 1, 'draft', 45),

    -- Bob's posts (Full-stack development)
    ('Modern JavaScript Frameworks Comparison', 'modern-javascript-frameworks-comparison', 'React, Vue, or Angular? This detailed comparison examines the strengths and weaknesses of the three major JavaScript frameworks. We''ll look at performance, learning curve, ecosystem, and real-world use cases to help you make an informed decision for your next project.', '2023-02-28', 2, 'published', 2103),
    ('Building Real-time Applications with WebSockets', 'building-realtime-applications-websockets', 'Real-time features are becoming essential in modern web applications. This tutorial covers implementing WebSockets with Django Channels, handling connection management, and building features like live chat, notifications, and collaborative editing.', '2023-03-15', 2, 'published', 1678),
    ('Frontend and Backend Integration Patterns', 'frontend-backend-integration-patterns', 'Exploring different approaches to integrate frontend and backend systems, including REST APIs, GraphQL, and real-time communication patterns.', '2023-04-10', 2, 'published', 934),
    ('Progressive Web Apps Development Guide', 'progressive-web-apps-development-guide', 'Learn how to build Progressive Web Apps that work offline, send push notifications, and provide native app-like experiences.', '2023-05-05', 2, 'draft', 67),

    -- Carol's posts (AI/ML focus)
    ('Machine Learning with Python: A Practical Guide', 'machine-learning-python-practical-guide', 'Machine learning doesn''t have to be intimidating. This practical guide introduces core ML concepts using Python libraries like scikit-learn, pandas, and numpy. We''ll build real projects including a recommendation system and predictive model.', '2023-03-25', 3, 'published', 1834),
    ('Data Visualization with Matplotlib and Seaborn', 'data-visualization-matplotlib-seaborn', 'Effective data visualization is crucial for data analysis and communication. This comprehensive tutorial covers creating stunning visualizations with Python''s most popular plotting libraries, from basic charts to interactive dashboards.', '2023-04-20', 3, 'published', 1267),
    ('Deep Learning Fundamentals', 'deep-learning-fundamentals', 'Introduction to neural networks, backpropagation, and building your first deep learning models with TensorFlow and PyTorch.', '2023-05-15', 3, 'published', 1543),
    ('Natural Language Processing with spaCy', 'natural-language-processing-spacy', 'Comprehensive guide to text processing and NLP tasks using the spaCy library for Python.', '2023-06-01', 3, 'draft', 23),

    -- David's posts (DevOps/Infrastructure)
    ('Docker Containerization Best Practices', 'docker-containerization-best-practices', 'Containerization has revolutionized software deployment. This guide covers Docker fundamentals, writing efficient Dockerfiles, multi-stage builds, and orchestration with Docker Compose. Learn how to containerize your applications following industry best practices.', '2023-04-12', 4, 'published', 1456),
    ('Kubernetes for Python Developers', 'kubernetes-python-developers', 'Kubernetes can seem complex, but it''s essential for modern application deployment. This developer-focused guide explains Kubernetes concepts through the lens of Python applications, covering deployments, services, and scaling strategies.', '2023-05-08', 4, 'published', 1289),
    ('CI/CD Pipelines with GitHub Actions', 'cicd-pipelines-github-actions', 'Automated testing and deployment are crucial for modern development workflows. Learn how to set up robust CI/CD pipelines using GitHub Actions.', '2023-06-03', 4, 'published', 876),
    ('Infrastructure as Code with Terraform', 'infrastructure-as-code-terraform', 'Managing infrastructure through code provides consistency, version control, and reproducibility.', '2023-07-01', 4, 'draft', 34),

    -- Emma's posts (Design/UX)
    ('Design Systems for Developers', 'design-systems-developers', 'Design systems bridge the gap between design and development. This guide explains how to create and maintain design systems that improve consistency, efficiency, and collaboration between design and development teams.', '2023-05-20', 5, 'published', 1123),
    ('Accessibility in Web Development', 'accessibility-web-development', 'Building accessible web applications isn''t just about compliance—it''s about creating inclusive experiences. This comprehensive guide covers WCAG guidelines, testing strategies, and practical implementation techniques.', '2023-06-15', 5, 'published', 987),
    ('CSS Grid and Flexbox Mastery', 'css-grid-flexbox-mastery', 'Modern CSS layout techniques that every developer should master. From basic concepts to advanced patterns.', '2023-07-10', 5, 'published', 754),
    ('User Experience Research Methods', 'user-experience-research-methods', 'Understanding your users is crucial for building successful products. This guide covers various UX research methods.', '2023-08-05', 5, 'draft', 12),

    -- Frank's posts (Startup/Business)
    ('Building MVP with Limited Resources', 'building-mvp-limited-resources', 'Starting a tech company requires making smart decisions about where to invest time and money. This article shares lessons learned from building multiple MVPs, including technology choices, feature prioritization, and validation strategies.', '2023-06-25', 6, 'published', 1567),
    ('Scaling Engineering Teams', 'scaling-engineering-teams', 'Growing from a solo developer to a full engineering organization presents unique challenges. Learn about hiring, team structure, communication, and maintaining culture during rapid growth.', '2023-07-20', 6, 'published', 1234),
    ('Technical Debt Management', 'technical-debt-management', 'Every startup accumulates technical debt. The key is managing it strategically rather than letting it become overwhelming.', '2023-08-15', 6, 'published', 698),
    ('Product-Market Fit for Technical Founders', 'product-market-fit-technical-founders', 'Technical founders often struggle with the business side. This guide helps engineers understand product-market fit.', '2023-09-10', 6, 'draft', 28),

    -- Grace's posts (Cloud/Architecture)
    ('Microservices Architecture Patterns', 'microservices-architecture-patterns', 'Microservices offer scalability and flexibility but introduce complexity. This comprehensive guide covers when to use microservices, common patterns, and pitfalls to avoid. We''ll explore service communication, data management, and monitoring strategies.', '2023-07-15', 7, 'published', 1678),
    ('Cloud-Native Application Development', 'cloud-native-application-development', 'Cloud-native development requires a different mindset than traditional application development. Learn about the principles, patterns, and tools that enable applications to thrive in cloud environments.', '2023-08-10', 7, 'published', 1345),
    ('Serverless Computing with AWS Lambda', 'serverless-computing-aws-lambda', 'Serverless computing abstracts away infrastructure management, allowing developers to focus on code. This guide covers AWS Lambda fundamentals.', '2023-09-05', 7, 'published', 923),
    ('Container Orchestration Strategies', 'container-orchestration-strategies', 'Comparing different approaches to container orchestration, from Docker Swarm to Kubernetes to cloud-managed services.', '2023-10-01', 7, 'draft', 15),

    -- Henry's posts (Security)
    ('Web Application Security Fundamentals', 'web-application-security-fundamentals', 'Security should be built into applications from the ground up, not added as an afterthought. This guide covers the OWASP Top 10, secure coding practices, and essential security testing techniques that every developer should know.', '2023-08-22', 8, 'published', 1456),
    ('API Security Best Practices', 'api-security-best-practices', 'APIs are increasingly becoming the primary attack vector for applications. Learn how to secure your APIs with proper authentication, authorization, rate limiting, and input validation techniques.', '2023-09-18', 8, 'published', 1234),
    ('Implementing Zero Trust Architecture', 'implementing-zero-trust-architecture', 'Zero Trust is becoming the standard for modern security architectures. This guide explains the principles and implementation strategies.', '2023-10-15', 8, 'published', 567),
    ('Penetration Testing for Developers', 'penetration-testing-developers', 'Understanding how attackers think helps developers build more secure applications. This introduction to penetration testing is designed for developers.', '2023-11-01', 8, 'draft', 89),

    -- Isabel's posts (Mobile Development)
    ('Cross-Platform Mobile Development Guide', 'cross-platform-mobile-development-guide', 'Building mobile apps for multiple platforms can be challenging. This comprehensive comparison of React Native, Flutter, and Xamarin helps you choose the right cross-platform solution for your project requirements.', '2023-09-12', 9, 'published', 1567),
    ('Mobile App Performance Optimization', 'mobile-app-performance-optimization', 'Mobile users expect fast, responsive applications. This guide covers performance optimization techniques for mobile apps, including image optimization, lazy loading, and efficient state management.', '2023-10-08', 9, 'published', 1123),
    ('Mobile UX Design Principles', 'mobile-ux-design-principles', 'Designing for mobile requires understanding unique constraints and opportunities. Learn about touch interfaces, screen sizes, and mobile-specific patterns.', '2023-11-05', 9, 'published', 789),
    ('Push Notifications Strategy', 'push-notifications-strategy', 'Effective push notification strategies that engage users without being annoying. This guide covers implementation and best practices.', '2023-11-20', 9, 'draft', 45),

    -- Jack's posts (Game Development)
    ('Game Development with Unity and Python', 'game-development-unity-python', 'While Unity primarily uses C#, Python can play important roles in game development through scripting, automation, and backend services. This article explores the intersection of Python and game development.', '2023-10-20', 10, 'published', 1234),
    ('3D Graphics Programming Fundamentals', '3d-graphics-programming-fundamentals', 'Understanding 3D graphics programming opens up possibilities in games, simulations, and visualization. This beginner-friendly introduction covers basic concepts, coordinate systems, and rendering pipelines.', '2023-11-15', 10, 'published', 987),
    ('Procedural Content Generation', 'procedural-content-generation', 'Procedural generation can create virtually unlimited content for games. Learn algorithms and techniques for generating worlds, levels, and assets.', '2023-12-01', 10, 'published', 654),
    ('Game Physics and Mathematics', 'game-physics-mathematics', 'Physics simulation is crucial for realistic games. This guide covers collision detection, rigid body dynamics, and mathematical foundations.', '2023-12-15', 10, 'draft', 23);

-- Update the database statistics
-- https://www.postgresql.org/docs/current/sql-analyze.html
ANALYZE author;
ANALYZE post;

-- Display summary of inserted data
SELECT
    'Authors' as table_name,
    COUNT(*) as total_records,
    MIN(created_at) as earliest_date,
    MAX(created_at) as latest_date
FROM author
UNION ALL
SELECT
    'Posts' as table_name,
    COUNT(*) as total_records,
    MIN(published_date) as earliest_date,
    MAX(published_date) as latest_date
FROM post;

-- Display status distribution
SELECT
    status,
    COUNT(*) as count,
    ROUND(AVG(read_count)) as avg_reads
FROM post
GROUP BY status
ORDER BY count DESC;

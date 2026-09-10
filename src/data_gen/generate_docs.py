#!/usr/bin/env python3
"""
Generate synthetic multilingual knowledge-base JSON documents for Sentiva products.
"""
import json
import os
import argparse
from datetime import datetime

# Multilingual content definitions
PRODUCTS = {
    "Sentiva Shield": {
        "en": {
            "overview": {
                "title": "Sentiva Shield - Advanced Multi-Device Security",
                "body": """Sentiva Shield is a comprehensive antivirus and multi-device security suite designed to protect your digital life across Windows, macOS, iOS, and Android platforms. With real-time threat detection, advanced malware protection, and ransomware defense, Shield ensures your devices stay secure from evolving cyber threats. Our AI-powered scanning engine identifies and neutralizes threats before they can harm your system. Features include web protection that blocks malicious websites, automatic security updates, and a user-friendly dashboard for managing all your devices in one place. Sentiva Shield combines enterprise-grade security with consumer simplicity."""
            },
            "pricing": {
                "title": "Sentiva Shield - Pricing Plans",
                "body": """Choose the right Sentiva Shield plan for your needs:

**Basic Plan** - $29.99/year (single device)
- Real-time antivirus protection
- Malware & spyware detection
- Automatic updates
- Email support

**Plus Plan** - $49.99/year (up to 5 devices)
- Everything in Basic, plus:
- Advanced ransomware protection
- Web protection & phishing defense
- VPN service (100MB/day)
- Priority support
- 24/7 threat monitoring

**Premium Plan** - $79.99/year (unlimited devices)
- Everything in Plus, plus:
- Unlimited VPN usage
- Password manager (100 entries)
- Secure file deletion
- System optimization tools
- Phone support
- Annual device security audit"""
            },
            "features": {
                "title": "Sentiva Shield - Key Features",
                "body": """**Core Protection**
- Real-time threat detection powered by machine learning
- Advanced malware & ransomware scanning
- Zero-day exploit prevention
- Boot-time scanning

**Web & Network Security**
- Blocks malicious websites and phishing attempts
- Safe browsing alerts
- DNS-level protection
- Public Wi-Fi security

**Device Management**
- Unified dashboard for multiple devices
- Remote device lock capability
- Lost device tracking
- Installation manager for safe downloads

**Performance**
- Lightweight agent with minimal system impact
- Scheduled scanning during idle times
- Optimized battery usage on mobile
- Fast threat signature updates

**Support & Updates**
- Automatic security definition updates
- Regular feature releases
- 24/7 threat intelligence updates"""
            },
            "setup": {
                "title": "Sentiva Shield - Installation & Setup",
                "body": """**Windows Installation:**
1. Download the installer from sentiva.com/shield
2. Run the .exe file as administrator
3. Accept the license agreement
4. Choose installation folder (default: C:\\Program Files\\Sentiva)
5. Click "Install" and wait for completion
6. Restart your computer when prompted
7. Launch Sentiva Shield from Start Menu
8. Activate with your license key or account credentials
9. Perform first full system scan

**macOS Installation:**
1. Download the .dmg installer
2. Open the installer and drag Sentiva Shield to Applications
3. Navigate to Applications and double-click Sentiva Shield
4. Grant necessary permissions when prompted
5. Complete the setup wizard
6. Sign in with your Sentiva account
7. Configure real-time protection settings

**Mobile Setup:**
- iOS: Download from App Store, sign in, enable notifications
- Android: Download from Google Play, grant permissions, activate"""
            },
            "privacy": {
                "title": "Sentiva Shield - Privacy & Data Handling",
                "body": """At Sentiva, we take your privacy seriously. Sentiva Shield collects minimal personal data necessary for security operations:

**Data We Collect:**
- Device identifiers (for multi-device management)
- Threat detection logs (for improving our engine)
- IP address and location (approximate, for geographical threat analysis)
- Application usage patterns (anonymous, for security analysis)

**Data We Do NOT Collect:**
- Browsing history
- Personal files or documents
- Passwords or payment information
- Email content

**Security Measures:**
- All data encrypted in transit (TLS 1.3)
- Encrypted storage on our servers
- No data sharing with third parties without explicit consent
- Automatic deletion after 90 days

**User Controls:**
- Opt-out of analytics collection
- Delete personal data anytime
- Export your data in standard formats
- Transparent privacy dashboard"""
            },
            "troubleshooting": {
                "title": "Sentiva Shield - Troubleshooting Guide",
                "body": """**Common Issues & Solutions:**

Q: Shield won't start after installation
A: Restart your computer. If problem persists, uninstall and reinstall, ensuring admin rights.

Q: False positive detections
A: Review detected files in Quarantine. Add safe files to exclusions via Settings > Exclusions. Report false positives to support@sentiva.com.

Q: High CPU usage
A: Disable real-time scanning during tasks. Configure scheduled scans during idle hours in Settings > Scan Schedule.

Q: License key not accepted
A: Ensure key is entered correctly. Check if license has expired. Download fresh key from your account.

Q: Mobile app crashes
A: Clear app cache via Settings > Apps. Reinstall from store.

Q: VPN connection fails
A: Restart VPN service. Select different server location. Check internet connection."""
            }
        },
        "ja": {
            "overview": {
                "title": "Sentiva Shield - 高度なマルチデバイスセキュリティ",
                "body": """Sentiva Shieldは、Windows、macOS、iOS、Androidプラットフォーム全体でデジタル生活を保護するための包括的なアンチウイルスおよびマルチデバイスセキュリティスイートです。リアルタイム脅威検出、高度なマルウェア保護、ランサムウェア防御により、デバイスを進化するサイバー脅威から安全に保ちます。当社のAI搭載スキャンエンジンは、脅威がシステムに害を与える前に識別して中和します。機能には、悪意のあるウェブサイトをブロックするウェブ保護、自動セキュリティ更新、およびすべてのデバイスを1か所で管理するユーザーフレンドリーなダッシュボードが含まれます。"""
            },
            "pricing": {
                "title": "Sentiva Shield - 価格プラン",
                "body": """ニーズに合ったSentiva Shieldプランを選択してください：

**ベーシックプラン** - ¥3,980/年（単一デバイス）
- リアルタイムアンチウイルス保護
- マルウェアとスパイウェア検出
- 自動更新
- メールサポート

**プラスプラン** - ¥6,980/年（最大5デバイス）
- ベーシックの全機能に加えて：
- 高度なランサムウェア保護
- ウェブ保護とフィッシング防御
- VPNサービス（1日100MB）
- 優先サポート

**プレミアムプラン** - ¥10,980/年（無制限デバイス）
- プラスの全機能に加えて：
- 無制限VPN使用
- パスワードマネージャー
- 安全なファイル削除
- システム最適化ツール"""
            },
            "features": {
                "title": "Sentiva Shield - 主要機能",
                "body": """**コア保護**
- 機械学習による脅威検出
- 高度なマルウェア・ランサムウェアスキャン
- ゼロデイエクスプロイト防止
- ブート時スキャン

**ウェブ・ネットワークセキュリティ**
- 悪意のあるウェブサイトとフィッシング対策
- 安全なブラウジングアラート
- DNS保護
- パブリックWi-Fiセキュリティ

**デバイス管理**
- 複数デバイスの統合ダッシュボード
- リモートデバイスロック
- 紛失デバイス追跡"""
            },
            "setup": {
                "title": "Sentiva Shield - インストールとセットアップ",
                "body": """**Windows インストール:**
1. sentiva.com/shieldからインストーラーをダウンロード
2. .exeファイルを管理者として実行
3. ライセンス契約に同意
4. インストールフォルダを選択
5. 「インストール」をクリックして完了を待つ
6. プロンプトが表示されたらコンピューターを再起動
7. スタートメニューからSentiva Shieldを起動
8. ライセンスキーでアクティベート

**macOS インストール:**
1. .dmgインストーラーをダウンロード
2. インストーラーを開いてアプリケーションにドラッグ
3. Applicationsから起動
4. 必要な権限を許可"""
            },
            "privacy": {
                "title": "Sentiva Shield - プライバシーとデータ処理",
                "body": """Sentivaではプライバシーを真摯に受け止めています。Sentiva Shieldはセキュリティ操作に必要な最小限の個人データのみを収集します：

**収集するデータ:**
- デバイス識別子
- 脅威検出ログ
- IP住所と位置情報（概算）
- アプリケーション使用パターン（匿名化）

**収集しないデータ:**
- ブラウジング履歴
- 個人ファイルまたはドキュメント
- パスワードまたは支払い情報
- メール内容

**セキュリティ対策:**
- 転送中のデータはTLS 1.3で暗号化
- サーバー上の暗号化ストレージ
- 明示的な同意なしに第三者との共有なし
- 90日後の自動削除"""
            },
            "troubleshooting": {
                "title": "Sentiva Shield - トラブルシューティングガイド",
                "body": """**一般的な問題と解決方法:**

Q: インストール後、Shieldが起動しない
A: コンピューターを再起動してください。問題が解決しない場合は、管理者権限でアンインストールして再インストールしてください。

Q: 誤検知が発生する
A: 「検疫」で検出されたファイルを確認してください。設定 > 除外に安全なファイルを追加してください。

Q: CPU使用率が高い
A: タスク中はリアルタイムスキャンを無効にしてください。

Q: ライセンスキーが受け入れられない
A: キーが正しく入力されていることを確認してください。有効期限を確認してください。"""
            }
        },
        "fr": {
            "overview": {
                "title": "Sentiva Shield - Sécurité Multi-Appareils Avancée",
                "body": """Sentiva Shield est une suite complète d'antivirus et de sécurité multi-appareils conçue pour protéger votre vie numérique sur les plateformes Windows, macOS, iOS et Android. Avec la détection des menaces en temps réel, la protection avancée contre les malwares et la défense contre les ransomwares, Shield garantit que vos appareils restent sécurisés contre les cybermenaces évolutives. Notre moteur de balayage alimenté par l'IA identifie et neutralise les menaces avant qu'elles ne puissent nuire à votre système. Les fonctionnalités incluent une protection Web qui bloque les sites malveillants, les mises à jour de sécurité automatiques et un tableau de bord convivial pour gérer tous vos appareils en un seul endroit."""
            },
            "pricing": {
                "title": "Sentiva Shield - Plans de Tarification",
                "body": """Choisissez le plan Sentiva Shield qui correspond à vos besoins :

**Plan Basic** - 29,99 €/an (appareil unique)
- Protection antivirus en temps réel
- Détection des malwares et spywares
- Mises à jour automatiques
- Support par e-mail

**Plan Plus** - 49,99 €/an (jusqu'à 5 appareils)
- Tout ce qui se trouve dans Basic, plus :
- Protection avancée contre les ransomwares
- Protection Web et défense contre le phishing
- Service VPN (100 Mo/jour)
- Support prioritaire

**Plan Premium** - 79,99 €/an (appareils illimités)
- Tout ce qui se trouve dans Plus, plus :
- Utilisation VPN illimitée
- Gestionnaire de mots de passe
- Suppression de fichiers sécurisée
- Outils d'optimisation système"""
            },
            "features": {
                "title": "Sentiva Shield - Caractéristiques Clés",
                "body": """**Protection Principale**
- Détection des menaces en temps réel alimentée par l'apprentissage automatique
- Balayage avancé des malwares et ransomwares
- Prévention des exploits zero-day
- Balayage au démarrage

**Sécurité Web et Réseau**
- Bloque les sites malveillants et les tentatives de phishing
- Alertes de navigation sécurisée
- Protection au niveau DNS
- Sécurité Wi-Fi public

**Gestion des Appareils**
- Tableau de bord unifié pour plusieurs appareils
- Verrouillage à distance des appareils
- Suivi des appareils perdus"""
            },
            "setup": {
                "title": "Sentiva Shield - Installation et Configuration",
                "body": """**Installation Windows :**
1. Téléchargez le programme d'installation depuis sentiva.com/shield
2. Exécutez le fichier .exe en tant qu'administrateur
3. Acceptez l'accord de licence
4. Choisissez le dossier d'installation
5. Cliquez sur « Installer » et attendez l'achèvement
6. Redémarrez votre ordinateur lorsqu'une notification s'affiche
7. Lancez Sentiva Shield depuis le menu Démarrage
8. Activez avec votre clé de licence

**Installation macOS :**
1. Téléchargez le programme d'installation .dmg
2. Ouvrez le programme d'installation et faites glisser vers Applications
3. Lancez depuis Applications
4. Accordez les permissions nécessaires"""
            },
            "privacy": {
                "title": "Sentiva Shield - Confidentialité et Traitement des Données",
                "body": """Chez Sentiva, nous prenons votre confidentialité au sérieux. Sentiva Shield collecte le minimum de données personnelles nécessaires aux opérations de sécurité :

**Données que nous Collectons :**
- Identifiants d'appareils
- Journaux de détection des menaces
- Adresse IP et localisation approximative
- Modèles d'utilisation d'applications (anonymisés)

**Données que nous NE Collectons PAS :**
- Historique de navigation
- Fichiers ou documents personnels
- Mots de passe ou informations de paiement
- Contenu des e-mails

**Mesures de Sécurité :**
- Toutes les données cryptées en transit (TLS 1.3)
- Stockage crypté sur nos serveurs
- Aucun partage de données avec des tiers sans consentement explicite
- Suppression automatique après 90 jours"""
            },
            "troubleshooting": {
                "title": "Sentiva Shield - Guide de Dépannage",
                "body": """**Problèmes Courants et Solutions :**

Q: Shield ne démarre pas après l'installation
A: Redémarrez votre ordinateur. Si le problème persiste, désinstallez et réinstallez en veillant à disposer des droits d'administrateur.

Q: Des détections fausses positives se produisent
A: Vérifiez les fichiers détectés dans Quarantaine. Ajoutez les fichiers sûrs aux exclusions via Paramètres > Exclusions.

Q: Utilisation élevée du CPU
A: Désactivez l'analyse en temps réel lors des tâches. Configurez les analyses programmées en Paramètres > Calendrier d'analyse.

Q: La clé de licence n'est pas acceptée
A: Assurez-vous que la clé est saisie correctement. Vérifiez si la licence a expiré."""
            }
        },
        "de": {
            "overview": {
                "title": "Sentiva Shield - Fortgeschrittene Multi-Device-Sicherheit",
                "body": """Sentiva Shield ist eine umfassende Antivirus- und Multi-Device-Sicherheitssuite, die Ihr digitales Leben auf Windows-, macOS-, iOS- und Android-Plattformen schützt. Mit Echtzeit-Bedrohungserkennung, fortgeschrittenem Malware-Schutz und Ransomware-Abwehr bleibt Shield vor sich entwickelnden Cyberbedrohungen geschützt. Unser KI-gestütztes Scanning-Engine erkennt und neutralisiert Bedrohungen, bevor sie Ihr System beschädigen können. Zu den Funktionen gehört Webschutz, der böswillige Websites blockiert, automatische Sicherheitsupdates und ein benutzerfreundliches Dashboard zum Verwalten aller Ihrer Geräte an einem Ort."""
            },
            "pricing": {
                "title": "Sentiva Shield - Preisgestaltung",
                "body": """Wählen Sie den Sentiva Shield-Plan, der Ihren Anforderungen entspricht:

**Basic-Plan** - 29,99 €/Jahr (einzelnes Gerät)
- Echtzeit-Antivirenschutz
- Malware- und Spyware-Erkennung
- Automatische Updates
- E-Mail-Support

**Plus-Plan** - 49,99 €/Jahr (bis zu 5 Geräte)
- Alles im Basic enthalten, plus:
- Fortgeschrittener Ransomware-Schutz
- Webschutz und Phishing-Abwehr
- VPN-Dienst (100 MB/Tag)
- Prioritätsunterstützung

**Premium-Plan** - 79,99 €/Jahr (unbegrenzte Geräte)
- Alles im Plus enthalten, plus:
- Unbegrenzte VPN-Nutzung
- Passwort-Manager
- Sichere Dateilöschung
- Systemoptimierungstools"""
            },
            "features": {
                "title": "Sentiva Shield - Hauptmerkmale",
                "body": """**Kernschutz**
- Echtzeit-Bedrohungserkennung mit maschinellem Lernen
- Fortgeschrittenes Malware- und Ransomware-Scanning
- Zero-Day-Exploit-Prävention
- Boot-Zeit-Scanning

**Web- und Netzwerksicherheit**
- Blockiert bösartige Websites und Phishing-Versuche
- Sichere Browsing-Warnungen
- DNS-Schutz
- Öffentliche Wi-Fi-Sicherheit

**Geräteverwaltung**
- Einheitliches Dashboard für mehrere Geräte
- Remote-Gerrätesperrung
- Verfolgung verlorener Geräte"""
            },
            "setup": {
                "title": "Sentiva Shield - Installation und Einrichtung",
                "body": """**Windows-Installation:**
1. Laden Sie das Installationsprogramm von sentiva.com/shield herunter
2. Führen Sie die .exe-Datei als Administrator aus
3. Akzeptieren Sie die Lizenzvereinbarung
4. Wählen Sie den Installationsordner
5. Klicken Sie auf „Installieren" und warten Sie auf die Fertigstellung
6. Starten Sie Ihren Computer neu, wenn Sie dazu aufgefordert werden
7. Starten Sie Sentiva Shield aus dem Startmenü
8. Aktivieren Sie mit Ihrem Lizenzschlüssel

**macOS-Installation:**
1. Laden Sie das .dmg-Installationsprogramm herunter
2. Öffnen Sie das Installationsprogramm und ziehen Sie es in Anwendungen
3. Starten Sie von Anwendungen
4. Erteilen Sie die erforderlichen Berechtigungen"""
            },
            "privacy": {
                "title": "Sentiva Shield - Datenschutz und Datenbehandlung",
                "body": """Bei Sentiva nehmen wir Ihren Datenschutz ernst. Sentiva Shield erfasst nur minimale persönliche Daten, die für Sicherheitsvorgänge erforderlich sind:

**Von uns erfasste Daten:**
- Gerätebezeichner
- Bedrohungserkennungsprotokolle
- IP-Adresse und ungefähre Standorte
- Nutzungsmuster für Anwendungen (anonym)

**Von uns NICHT erfasste Daten:**
- Browsing-Verlauf
- Persönliche Dateien oder Dokumente
- Passwörter oder Zahlungsinformationen
- E-Mail-Inhalte

**Sicherheitsmaßnahmen:**
- Alle Daten während der Übertragung verschlüsselt (TLS 1.3)
- Verschlüsserte Speicherung auf unseren Servern
- Keine Datenweitergabe an Dritte ohne ausdrückliche Zustimmung
- Automatisches Löschen nach 90 Tagen"""
            },
            "troubleshooting": {
                "title": "Sentiva Shield - Fehlerbehebungsanleitung",
                "body": """**Häufige Probleme und Lösungen:**

F: Shield wird nach der Installation nicht gestartet
A: Starten Sie Ihren Computer neu. Wenn das Problem weiterhin besteht, deinstallieren und reinstallieren Sie es, um sicherzustellen, dass Sie über Administratorrechte verfügen.

F: Es treten falsch positive Erkennungen auf
A: Überprüfen Sie die erkannten Dateien in Quarantäne. Fügen Sie sichere Dateien über Einstellungen > Ausschlüsse hinzu.

F: Hohe CPU-Auslastung
A: Deaktivieren Sie die Echtzeitanalyse während Aufgaben. Konfigurieren Sie geplante Scans über Einstellungen > Scan-Zeitplan.

F: Der Lizenzschlüssel wird nicht akzeptiert
A: Stellen Sie sicher, dass der Schlüssel korrekt eingegeben wird. Überprüfen Sie, ob die Lizenz abgelaufen ist."""
            }
        }
    },
    "Sentiva Alert": {
        "en": {
            "overview": {
                "title": "Sentiva Alert - Scam & Fraud Detection",
                "body": """Sentiva Alert is an intelligent scam and fraud detection system that protects you from text message scams, fraudulent phone calls, fake websites, and deepfake audio/video. Using machine learning and behavioral analysis, Sentiva Alert identifies suspicious communications in real-time and alerts you before you become a victim. The service integrates with your phone to analyze incoming calls and messages, checks URLs against a constantly updated database of fraudulent sites, and uses voice analysis to detect spoofed calls. Available on iOS and Android, Sentiva Alert provides peace of mind in an increasingly dangerous digital landscape."""
            },
            "pricing": {
                "title": "Sentiva Alert - Pricing Plans",
                "body": """**Free Plan**
- Basic SMS scam detection
- Call screening (limited to known threats)
- Mobile app with notifications
- Web portal access

**Plus Plan** - $9.99/month
- Everything in Free, plus:
- Advanced fraud URL detection
- Deepfake audio detection
- Enhanced call analysis
- Priority support
- Monthly fraud report
- Up to 3 phone numbers

**Premium Plan** - $19.99/month
- Everything in Plus, plus:
- Unlimited phone numbers
- Family protection (5 users)
- Dark web monitoring for your phone number
- Custom fraud rules
- Real-time chat support
- Quarterly security briefings"""
            },
            "features": {
                "title": "Sentiva Alert - Key Features",
                "body": """**SMS & Message Protection**
- Real-time text message scam detection
- URL scanning in messages
- Sender reputation analysis
- Suspicious pattern recognition

**Call Screening**
- Incoming call verification
- Spoofed call detection
- Voice pattern analysis
- Known scammer database

**Deepfake Detection**
- Audio deepfake analysis
- Video deepfake alerts
- Biometric spoofing detection

**Web Protection**
- Phishing website detection
- Fake banking site identification
- Online auction fraud protection
- E-commerce scam detection

**User Dashboard**
- View blocked threats
- Manage whitelist/blacklist
- Set custom detection rules
- Export threat reports"""
            }
        },
        "ja": {
            "overview": {
                "title": "Sentiva Alert - 詐欺検出システム",
                "body": """Sentiva Alertは、テキストメッセージ詐欺、詐欺電話、偽のウェブサイト、およびディープフェイク音声/ビデオから保護するインテリジェント詐欺検出システムです。機械学習と行動分析を使用して、Sentiva Alertは疑わしい通信をリアルタイムで識別し、被害者になる前に警告します。このサービスはあなたの電話と統合して、着信通話とメッセージを分析し、詐欺的なサイトの常に更新されるデータベースに対してURLをチェックし、音声分析を使用してなりすまし通話を検出します。"""
            },
            "pricing": {
                "title": "Sentiva Alert - 価格プラン",
                "body": """**無料プラン**
- 基本的なSMS詐欺検出
- 通話スクリーニング（既知の脅威に限定）
- 通知機能付きモバイルアプリ
- ウェブポータルアクセス

**プラスプラン** - ¥1,200/月
- 無料プランの全機能に加えて：
- 高度な詐欺URL検出
- ディープフェイク音声検出
- 強化された通話分析
- 優先サポート
- 月間詐欺レポート

**プレミアムプラン** - ¥2,500/月
- プラスの全機能に加えて：
- 無制限の電話番号
- ファミリー保護（5ユーザー）
- ダークウェブ監視
- カスタム詐欺ルール
- 24/7チャットサポート"""
            },
            "features": {
                "title": "Sentiva Alert - 主要機能",
                "body": """**SMS・メッセージ保護**
- リアルタイムテキストメッセージ詐欺検出
- メッセージ内のURL スキャン
- 送信者評判分析
- 疑わしいパターン認識

**通話スクリーニング**
- 着信通話検証
- なりすまし通話検出
- 音声パターン分析
- 既知の詐欺師データベース

**ディープフェイク検出**
- 音声ディープフェイク分析
- ビデオディープフェイク警告"""
            }
        },
        "fr": {
            "overview": {
                "title": "Sentiva Alert - Détection des Fraudes",
                "body": """Sentiva Alert est un système intelligent de détection des fraudes et arnaques qui vous protège contre les SMS frauduleux, les appels téléphoniques frauduleux, les faux sites Web et les audio/vidéos deepfake. En utilisant l'apprentissage automatique et l'analyse comportementale, Sentiva Alert identifie les communications suspectes en temps réel et vous alerte avant que vous ne deveniez une victime. Le service s'intègre à votre téléphone pour analyser les appels et les messages entrants, vérifie les URL par rapport à une base de données constamment mise à jour de sites frauduleux."""
            },
            "pricing": {
                "title": "Sentiva Alert - Plans de Tarification",
                "body": """**Plan Gratuit**
- Détection basique des fraudes par SMS
- Filtrage des appels (limité aux menaces connues)
- Application mobile avec notifications
- Accès au portail Web

**Plan Plus** - 9,99 €/mois
- Tout ce qui se trouve dans Gratuit, plus :
- Détection avancée des URL frauduleuses
- Détection des deepfakes audio
- Analyse d'appels améliorée
- Support prioritaire
- Rapport mensuel sur les fraudes

**Plan Premium** - 19,99 €/mois
- Tout ce qui se trouve dans Plus, plus :
- Numéros de téléphone illimités
- Protection familiale (5 utilisateurs)
- Surveillance du dark web
- Règles de fraude personnalisées
- Support chat en temps réel"""
            },
            "features": {
                "title": "Sentiva Alert - Caractéristiques Clés",
                "body": """**Protection des SMS et des Messages**
- Détection des arnaquages par message texte en temps réel
- Analyse des URL dans les messages
- Analyse de la réputation de l'expéditeur
- Reconnaissance des modèles suspects

**Filtrage des Appels**
- Vérification des appels entrants
- Détection des appels usurpés
- Analyse des modèles vocaux
- Base de données des arnaqueurs connus

**Détection des Deepfakes**
- Analyse des deepfakes audio
- Alertes vidéo deepfake"""
            }
        },
        "de": {
            "overview": {
                "title": "Sentiva Alert - Betrugserkennung",
                "body": """Sentiva Alert ist ein intelligentes System zur Erkennung von Betrügereien und Betrug, das Sie vor SMS-Betrügereien, betrügerischen Telefonanrufen, gefälschten Websites und Deepfake-Audio/Video schützt. Mit Hilfe von maschinellem Lernen und Verhaltensanalyse erkennt Sentiva Alert verdächtige Mitteilungen in Echtzeit und warnt Sie, bevor Sie Opfer werden."""
            },
            "pricing": {
                "title": "Sentiva Alert - Preisgestaltung",
                "body": """**Kostenlos**
- Grundlegende SMS-Betrugs erkennung
- Anruffilterung (auf bekannte Bedrohungen beschränkt)
- Mobile App mit Benachrichtigungen
- Web-Portal-Zugriff

**Plus-Plan** - 9,99 €/Monat
- Alles im kostenlosen Plan, plus:
- Erweiterte Erkennung betrügerischer URLs
- Deepfake-Audionachweise
- Verbesserte Anrufanalyse
- Priorität Support

**Premium-Plan** - 19,99 €/Monat
- Alles im Plus-Plan, plus:
- Unbegrenzte Telefonnummern
- Familienschutz (5 Benutzer)
- Dark Web Monitoring"""
            },
            "features": {
                "title": "Sentiva Alert - Hauptmerkmale",
                "body": """**SMS- und Nachrichtenschutz**
- Echtzeit-SMS-Betrugs erkennung
- URL-Analyse in Nachrichten
- Absenderreputationsanalyse

**Anruffilterung**
- Eingehende Anrufprüfung
- Erkennung gefälschter Anrufe
- Sprachmusteranalyse

**Deepfake-Erkennung**
- Audio-Deepfake-Analyse
- Video-Deepfake-Warnungen"""
            }
        }
    }
}

# Continue with remaining products in next part - simplified for brevity
OTHER_PRODUCTS_CONTENT = {
    "Sentiva Family": {
        "en": {"overview": {"title": "Sentiva Family - AI Family Safety", "body": "Sentiva Family is an AI-powered family safety assistant that helps parents protect their children online. Features include smart parental controls, real-time screen monitoring, automatic privacy masking, and kid-safe browsing recommendations. Set time limits, manage app access, filter content, and receive alerts about suspicious activities."}},
        "ja": {"overview": {"title": "Sentiva Family - AI ファミリーセーフティ", "body": "Sentiva Familyは、保護者がお子様をオンラインで保護するのを支援するAI搭載のファミリーセーフティアシスタントです。スマートな保護者向けコントロール、リアルタイムスクリーン監視、自動プライバシーマスキング、子ども向けブラウジング推奨事項が含まれます。"}},
        "fr": {"overview": {"title": "Sentiva Family - Sécurité Famille IA", "body": "Sentiva Family est un assistant de sécurité familiale alimenté par l'IA qui aide les parents à protéger leurs enfants en ligne. Les fonctionnalités incluent des contrôles parentaux intelligents, une surveillance d'écran en temps réel, un masquage automatique de la confidentialité et des recommandations de navigation adaptée aux enfants."}},
        "de": {"overview": {"title": "Sentiva Family - KI-Familiensicherheit", "body": "Sentiva Family ist ein KI-gestützter Familiensicherheits-Assistent, der Eltern hilft, ihre Kinder online zu schützen. Zu den Funktionen gehören intelligente elterliche Kontrollen, Echtzeit-Bildschirmüberwachung und automatische Datenschutzausblendung."}}
    },
    "Sentiva ID": {
        "en": {"overview": {"title": "Sentiva ID - Identity & Data Protection", "body": "Sentiva ID protects your personal information and digital identity. Features include VPN service, dark web monitoring, credential breach alerts, identity theft insurance, and secure password storage. Monitor your online presence, receive alerts about compromised accounts, and restore your identity if needed."}},
        "ja": {"overview": {"title": "Sentiva ID - 個人情報・データ保護", "body": "Sentiva IDはあなたの個人情報とデジタルアイデンティティを保護します。VPNサービス、ダークウェブ監視、認証情報漏洩アラート、身元盗難保険、安全なパスワード保存などの機能が含まれます。"}},
        "fr": {"overview": {"title": "Sentiva ID - Protection de l'Identité et des Données", "body": "Sentiva ID protège vos informations personnelles et votre identité numérique. Les fonctionnalités incluent le service VPN, la surveillance du dark web, les alertes de violations d'informations d'identification, l'assurance contre le vol d'identité et le stockage sécurisé des mots de passe."}},
        "de": {"overview": {"title": "Sentiva ID - Identitäts- und Datenschutz", "body": "Sentiva ID schützt Ihre persönlichen Informationen und digitale Identität. Funktionen umfassen VPN-Service, Dark-Web-Überwachung, Warnungen bei Benutzerda tenverletzungen und sichere Passwort speicherung."}}
    },
    "Sentiva Scan": {
        "en": {"overview": {"title": "Sentiva Scan - Free Security Check", "body": "Sentiva Scan is a free online security diagnostic tool that analyzes your device for vulnerabilities, outdated software, weak passwords, and security misconfigurations. Receive a detailed report with actionable recommendations to improve your security posture. No registration required, completely free, and runs directly in your browser."}},
        "ja": {"overview": {"title": "Sentiva Scan - 無料セキュリティチェック", "body": "Sentiva Scanは、デバイスの脆弱性、古いソフトウェア、弱いパスワード、セキュリティの設定ミスを分析する無料のオンラインセキュリティ診断ツールです。登録不要、完全に無料です。"}},
        "fr": {"overview": {"title": "Sentiva Scan - Contrôle de Sécurité Gratuit", "body": "Sentiva Scan est un outil de diagnostic de sécurité en ligne gratuit qui analyse votre appareil pour détecter les vulnérabilités, les logiciels obsolètes, les mots de passe faibles et les erreurs de configuration de sécurité."}},
        "de": {"overview": {"title": "Sentiva Scan - Kostenlose Sicherheitsprüfung", "body": "Sentiva Scan ist ein kostenloses Online-Sicherheits-Diagnosetool, das Ihr Gerät auf Sicherheitslücken, veraltete Software, schwache Passwörter und Sicherheitskonfigurationsfehler analysiert."}}
    }
}

def generate_extended_content():
    """Generate extended multilingual content for all products and categories."""
    docs = []

    # Process Sentiva Shield (already has full content)
    for lang, categories in PRODUCTS["Sentiva Shield"].items():
        for category, content_data in categories.items():
            doc_id = f"sentiva-shield-{category}-{lang}"
            doc = {
                "doc_id": doc_id,
                "product": "Sentiva Shield",
                "lang": lang,
                "category": category,
                "title": content_data["title"],
                "source_uri": f"sentiva-kb://shield/{category}",
                "body": content_data["body"],
                "faqs": [
                    {"q": "Is Sentiva Shield compatible with my device?", "a": "Sentiva Shield supports Windows 10+, macOS 10.14+, iOS 12+, and Android 8+."}
                ] if lang == "en" else [],
                "metadata": {
                    "plan_tiers": ["Basic", "Plus", "Premium"],
                    "supported_platforms": ["Windows", "macOS", "iOS", "Android"],
                    "last_updated": "2026-08-15"
                }
            }
            docs.append(doc)

    # Process Sentiva Alert
    for lang, categories in PRODUCTS["Sentiva Alert"].items():
        for category, content_data in categories.items():
            doc_id = f"sentiva-alert-{category}-{lang}"
            doc = {
                "doc_id": doc_id,
                "product": "Sentiva Alert",
                "lang": lang,
                "category": category,
                "title": content_data["title"],
                "source_uri": f"sentiva-kb://alert/{category}",
                "body": content_data["body"],
                "faqs": [],
                "metadata": {
                    "supported_platforms": ["iOS", "Android"],
                    "last_updated": "2026-08-15"
                }
            }
            docs.append(doc)

    # Process remaining products - overview only for this part
    for product_name, product_content in OTHER_PRODUCTS_CONTENT.items():
        for lang, categories in product_content.items():
            for category, content_data in categories.items():
                product_slug = product_name.lower().replace(" ", "-")
                doc_id = f"{product_slug}-{category}-{lang}"
                doc = {
                    "doc_id": doc_id,
                    "product": product_name,
                    "lang": lang,
                    "category": category,
                    "title": content_data["title"],
                    "source_uri": f"sentiva-kb://{product_slug}/{category}",
                    "body": content_data["body"],
                    "faqs": [],
                    "metadata": {
                        "last_updated": "2026-08-15"
                    }
                }
                docs.append(doc)

    return docs

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic multilingual Sentiva knowledge-base docs")
    parser.add_argument("--out", default="src/data_gen/output/raw_json", help="Output directory for JSON files")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    docs = generate_extended_content()

    for doc in docs:
        filepath = os.path.join(args.out, f"{doc['doc_id']}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(docs)} JSON documents in {args.out}")
    return docs

if __name__ == "__main__":
    main()

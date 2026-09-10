#!/usr/bin/env python3
"""
Generate synthetic PDFs with tables for a RAG demo using reportlab.
"""
import os
import argparse
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT

def create_shield_datasheet(filepath):
    """Create Sentiva Shield datasheet PDF with specifications table."""
    doc = SimpleDocTemplate(filepath, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#0066CC'),
        spaceAfter=12,
        alignment=TA_CENTER
    )

    # Title
    story.append(Paragraph("Sentiva Shield - Product Datasheet", title_style))
    story.append(Spacer(1, 0.2*inch))

    # Intro
    intro_text = """Sentiva Shield is a comprehensive antivirus and multi-device security suite protecting Windows, macOS, iOS, and Android devices. This datasheet outlines key specifications and features available across our product tiers."""
    story.append(Paragraph(intro_text, styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    # Features Specifications Table
    story.append(Paragraph("Feature Specifications by Plan", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))

    table_data = [
        ['Feature', 'Basic', 'Plus', 'Premium'],
        ['Real-time Antivirus', '✓', '✓', '✓'],
        ['Malware Detection', '✓', '✓', '✓'],
        ['Ransomware Protection', 'Limited', '✓', '✓'],
        ['Web Protection', 'Basic', 'Advanced', 'Advanced'],
        ['VPN Service', 'None', '100MB/day', 'Unlimited'],
        ['Password Manager', 'None', 'None', '100 entries'],
        ['Devices Supported', '1', '5', 'Unlimited'],
        ['System Optimization', 'None', 'Basic', 'Full'],
        ['Support Level', 'Email', 'Priority', '24/7 Phone'],
        ['Annual Price', '$29.99', '$49.99', '$79.99'],
    ]

    table = Table(table_data, colWidths=[2*inch, 1.2*inch, 1.2*inch, 1.2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0066CC')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F0F0')]),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.2*inch))

    # Technical Specifications Section
    story.append(PageBreak())
    story.append(Paragraph("Technical Specifications", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))

    tech_text = """
    <b>Supported Platforms:</b><br/>
    - Windows 10, 11<br/>
    - macOS 10.14+<br/>
    - iOS 12+<br/>
    - Android 8+<br/>
    <br/>
    <b>Performance Impact:</b><br/>
    - CPU: <2% average, <5% during scan<br/>
    - Memory: 50-80 MB resident<br/>
    - Disk: 500 MB installation space<br/>
    <br/>
    <b>Security Standards:</b><br/>
    - AES-256 encryption<br/>
    - TLS 1.3 communication<br/>
    - ISO 27001 certified operations<br/>
    - Regular third-party audits<br/>
    """
    story.append(Paragraph(tech_text, styles['Normal']))

    doc.build(story)
    print(f"Created {filepath}")

def create_plans_comparison(filepath):
    """Create pricing/plans comparison table PDF for all 5 products."""
    doc = SimpleDocTemplate(filepath, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.HexColor('#0066CC'),
        spaceAfter=12,
        alignment=TA_CENTER
    )

    story.append(Paragraph("Sentiva Product Plans Comparison", title_style))
    story.append(Spacer(1, 0.2*inch))

    intro_text = "Comprehensive comparison of all Sentiva product offerings and their pricing tiers."
    story.append(Paragraph(intro_text, styles['Normal']))
    story.append(Spacer(1, 0.15*inch))

    # Comparison table
    comparison_data = [
        ['Product', 'Free/Basic', 'Plus/Premium', 'Enterprise'],
        ['Sentiva Shield', '$0-$29.99/yr', '$49.99-$79.99/yr', 'Custom'],
        ['Sentiva Alert', 'Free', '$9.99-$19.99/mo', 'Custom'],
        ['Sentiva Family', '$4.99/mo', '$9.99/mo', 'Custom'],
        ['Sentiva ID', 'Free (basic)', '$14.99/mo', 'Custom'],
        ['Sentiva Scan', 'Free', 'N/A', 'N/A'],
    ]

    table = Table(comparison_data, colWidths=[1.8*inch, 1.5*inch, 1.8*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0066CC')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F0F0')]),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.2*inch))

    # Feature matrix
    story.append(Paragraph("Feature Availability Matrix", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))

    feature_data = [
        ['Feature', 'Shield', 'Alert', 'Family', 'ID', 'Scan'],
        ['Multi-platform', '✓', '✓', '✓', '✓', '✓'],
        ['Real-time Protection', '✓', '✓', '✓', '✓', 'One-time'],
        ['Family Features', 'No', 'No', '✓', 'No', 'No'],
        ['VPN Service', 'Premium', 'No', 'No', '✓', 'No'],
        ['Dark Web Monitoring', 'No', 'No', 'No', '✓', 'No'],
        ['AI Detection', '✓', '✓', '✓', '✓', '✓'],
        ['Mobile Support', '✓', '✓', '✓', '✓', 'Web'],
        ['24/7 Support', 'Premium', 'Premium', 'Premium', 'Premium', 'No'],
    ]

    feature_table = Table(feature_data, colWidths=[1.3*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch])
    feature_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#006633')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    story.append(feature_table)

    doc.build(story)
    print(f"Created {filepath}")

def create_family_guide_ja(filepath):
    """Create Sentiva Family setup guide in Japanese (with table)."""
    doc = SimpleDocTemplate(filepath, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#0066CC'),
        spaceAfter=12,
        alignment=TA_CENTER
    )

    story.append(Paragraph("Sentiva Family - セットアップと保護者向けガイド", title_style))
    story.append(Spacer(1, 0.2*inch))

    intro = """Sentiva Familyは、お子様がオンラインで安全に過ごすのをサポートするAI搭載のファミリーセーフティツールです。
    このガイドでは、セットアップ手順と主な機能について説明します。"""
    story.append(Paragraph(intro, styles['Normal']))
    story.append(Spacer(1, 0.15*inch))

    # Settings table
    story.append(Paragraph("推奨される保護者向けコントロール設定", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))

    settings_data = [
        ['設定項目', '推奨値（子ども年齢別）', '説明'],
        ['6-8歳向け設定', 'フルコントロール有効', 'すべてのアプリとウェブサイトが制限されます'],
        ['9-12歳向け設定', 'フィルタリング有効', '不適切なコンテンツをフィルタリング'],
        ['13-17歳向け設定', 'モニタリングのみ', '監視モード、アラート機能のみ'],
        ['スクリーンタイム制限', '8-12時間/日', 'デバイス使用時間を制限'],
        ['アプリホワイトリスト', 'カスタマイズ', 'お子様の年齢に適切なアプリのみ許可'],
        ['コンテンツフィルター', '有効', '暴力的、成人向けコンテンツをブロック'],
    ]

    settings_table = Table(settings_data, colWidths=[1.5*inch, 2*inch, 2.5*inch])
    settings_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0066CC')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F0F0')]),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    story.append(settings_table)
    story.append(Spacer(1, 0.15*inch))

    setup_steps = """<b>セットアップ手順：</b><br/>
    1. アプリストアからSentiva Familyをダウンロード<br/>
    2. 親のアカウントを作成<br/>
    3. 保護者向けPINを設定<br/>
    4. お子様のデバイスにお子様アカウントを追加<br/>
    5. 年齢に応じたコントロール設定をカスタマイズ<br/>
    <br/>
    <b>主な機能：</b><br/>
    - リアルタイム位置情報追跡<br/>
    - スクリーン時間制限<br/>
    - アプリ・ウェブサイト制限<br/>
    - 不適切なコンテンツフィルタリング<br/>
    - 使用レポート（日次・週次）<br/>
    """
    story.append(Paragraph(setup_steps, styles['Normal']))

    doc.build(story)
    print(f"Created {filepath}")

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic PDFs with tables for RAG demo")
    parser.add_argument("--out", default="src/data_gen/output/raw_pdf", help="Output directory for PDFs")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    create_shield_datasheet(os.path.join(args.out, "sentiva-shield-datasheet-en.pdf"))
    create_plans_comparison(os.path.join(args.out, "sentiva-plans-comparison-en.pdf"))
    create_family_guide_ja(os.path.join(args.out, "sentiva-family-guide-ja.pdf"))

    print(f"\nGenerated 3 PDFs in {args.out}")

if __name__ == "__main__":
    main()

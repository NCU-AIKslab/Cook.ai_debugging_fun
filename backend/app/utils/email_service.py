"""
Email 發送服務

提供發送驗證碼郵件的功能，用於學生註冊時的信箱驗證。
"""

import os
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


def generate_verification_code() -> str:
    """
    生成 6 位數的隨機驗證碼
    
    Returns:
        str: 6 位數字驗證碼
    """
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])


def send_verification_email(to_email: str, verification_code: str) -> bool:
    """
    發送驗證碼郵件
    
    Args:
        to_email: 收件人 Email
        verification_code: 6 位數驗證碼
        
    Returns:
        bool: 發送成功返回 True，失敗返回 False
    """
    # 從環境變數取得 SMTP 設定
    smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    
    if not smtp_user or not smtp_password:
        print("錯誤: 未設定 SMTP_USER 或 SMTP_PASSWORD 環境變數")
        return False
    
    # 建立郵件內容
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Cook.ai 學生註冊驗證碼'
    msg['From'] = smtp_user
    msg['To'] = to_email
    
    # 純文字版本
    text_content = f"""
您好，

您正在註冊 Cook.ai 學生帳號。

您的驗證碼是: {verification_code}

此驗證碼將在 10 分鐘後失效。

如果這不是您的操作，請忽略此郵件。

Cook.ai 團隊
"""
    
    # HTML 版本
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Arial', 'Microsoft JhengHei', sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 10px 10px 0 0;
        }}
        .content {{
            background: white;
            padding: 30px;
            border-radius: 0 0 10px 10px;
        }}
        .code-box {{
            background: #f0f0f0;
            border: 2px dashed #667eea;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            margin: 20px 0;
        }}
        .code {{
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
            letter-spacing: 8px;
        }}
        .footer {{
            text-align: center;
            color: #999;
            font-size: 12px;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Cook.ai 學生註冊</h1>
        </div>
        <div class="content">
            <p>您好，</p>
            <p>您正在註冊 Cook.ai 學生帳號。請使用以下驗證碼完成註冊：</p>
            
            <div class="code-box">
                <div class="code">{verification_code}</div>
            </div>
            
            <p><strong>注意事項：</strong></p>
            <ul>
                <li>此驗證碼將在 <strong>10 分鐘</strong>後失效</li>
                <li>請勿將驗證碼分享給他人</li>
                <li>如果這不是您的操作，請忽略此郵件</li>
            </ul>
            
            <div class="footer">
                <p>Cook.ai 團隊</p>
            </div>
        </div>
    </div>
</body>
</html>
"""
    
    # 加入純文字和 HTML 版本
    part1 = MIMEText(text_content, 'plain', 'utf-8')
    part2 = MIMEText(html_content, 'html', 'utf-8')
    msg.attach(part1)
    msg.attach(part2)
    
    try:
        # 連接 SMTP 伺服器並發送郵件
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        print(f"驗證碼郵件已成功發送至 {to_email}")
        return True
        
    except Exception as e:
        print(f"發送郵件失敗: {str(e)}")
        return False

# 🎤 Deep Trip - Voice-Powered Travel Assistant

Vox Tokyo Hackathon 2024 Project
Track: ⛩️ Omotenashi AI — Immersive AI guide for tourists exploring Japan's hidden gems

## プロジェクト概要
音声による旅行アシストAI「Deep Trip」を開発します。観光客が音声で簡単に旅行情報を取得し、日本の隠れた名所を探索できる没入型音声ガイドを提供します。
MiniMaxとTenframework (Agora) を活用し、リアルタイムで自然な対話を実現します。

## 主な機能
- 🎙️ **リアルタイム音声対話**: 低遅延の音声対話でストレスのないガイド体験
- 🗾 **隠れた名所の案内**: 一般的な観光地ではない、深い日本体験の提案
- 🤝 **おもてなしAI**: 文化的な背景やマナーも含めた丁寧なガイド
- 📍 **位置情報連動**: 現在地に基づいたスポット紹介

## 技術スタック
- **言語**: Python
- **AIモデル**: MiniMax (Emotionally expressive, natural Japanese speech synthesis)
- **フレームワーク**: Tenframework (Agora - Ultra-low latency real-time voice SDK)
- **その他**: FastAPI, WebSockets

## セットアップ

### 1. 仮想環境の構築
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows
```

### 2. 依存関係のインストール
```bash
pip install -r requirements.txt
```

### 3. 実行
```bash
python main.py
```

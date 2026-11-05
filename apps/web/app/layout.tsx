import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "蓝图智匠 · AEC Copilot",
  description: "自然语言驱动的可验证建模工作台",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}

import React from 'react';

const Footer: React.FC = () => {
  return (
    <footer className="flex-shrink-0 bg-neutral-footer-bg text-white py-2 px-8 text-sm">
      <div className="max-w-7xl mx-auto flex justify-center items-center gap-10">

        {/* Lab info */}
        <div className="flex flex-col text-center gap-1">
          <p className="font-medium text-neutral-text-on-dark">國立中央大學 人工智慧與知識系統實驗室</p>
          <p className="text-neutral-footer-text">NCU Artificial Intelligence & Knowledge System Lab</p>
        </div>

        {/* Divider */}
        <div className="h-12 w-px bg-neutral-footer-border"></div>

        {/* Developers */}
        <div className="flex flex-col text-center gap-1">
          <p className="text-neutral-footer-text">開發者：陳淳瑜、陳玟樺、劉品媛</p>
          <p className="text-neutral-footer-text">指導教授：楊鎮華 教授</p>
        </div>

        <div className="h-12 w-px bg-neutral-footer-border"></div>

        {/* Contact */}
        <div className="flex flex-col text-center gap-1">
          <p className="text-neutral-text-tertiary text-xs">地址：(320317) 桃園市中壢區中大路300號 國立中央大學工程五館 E6-B320</p>
          <p className="text-neutral-text-tertiary text-xs">Tel：03 - 4227151 分機 : 35353</p>
        </div>

      </div>
    </footer>
  );
};

export default Footer;
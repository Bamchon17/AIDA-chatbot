"use client";

import Image from "next/image";

interface AvatarProps {
  avatarSrc?: string;
}

export default function Avatar({ 
  avatarSrc = "/AIDA.png"
}: AvatarProps) {
  return (
    <div className="relative flex h-full w-full items-center justify-center md:justify-end overflow-hidden">
      {/* Avatar PNG */}
      <div className="relative z-10 flex items-center justify-center md:translate-x-35 translate-y-3">
        <Image
          src={avatarSrc}
          alt="Virtual AI Avatar"
          width={800}
          height={1000}
          
          className="object-contain max-h-[30vh] md:max-h-[80vh]"
          priority
          onError={(e) => {
            e.currentTarget.style.display = 'none';
          }}
        />
      </div>
    </div>
  );
}

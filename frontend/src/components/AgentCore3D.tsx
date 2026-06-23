import React, { useRef, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { MeshDistortMaterial, Sphere, PointMaterial } from '@react-three/drei';
import * as THREE from 'three';

function AgentSphere() {
  const meshRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  // Animate the 3D orb based on time and mouse pointer coordinates
  useFrame((state) => {
    if (!meshRef.current) return;
    
    // Slow ambient rotation
    meshRef.current.rotation.x += 0.003;
    meshRef.current.rotation.y += 0.005;
    
    // Mouse coordinates mapped to scale-appropriate 3D coordinate space
    const x = state.pointer.x * 1.5;
    const y = state.pointer.y * 1.5;
    
    // Smoothly interpolate (lerp) the position to chase the mouse pointer
    meshRef.current.position.x = THREE.MathUtils.lerp(meshRef.current.position.x, x, 0.1);
    meshRef.current.position.y = THREE.MathUtils.lerp(meshRef.current.position.y, y, 0.1);
    
    // Pulsing effect when hovered
    const scaleVal = hovered ? 1.45 : 1.1;
    meshRef.current.scale.x = THREE.MathUtils.lerp(meshRef.current.scale.x, scaleVal, 0.1);
    meshRef.current.scale.y = THREE.MathUtils.lerp(meshRef.current.scale.y, scaleVal, 0.1);
    meshRef.current.scale.z = THREE.MathUtils.lerp(meshRef.current.scale.z, scaleVal, 0.1);
  });

  return (
    <Sphere
      ref={meshRef}
      args={[1.1, 64, 64]}
      onPointerOver={() => setHovered(true)}
      onPointerOut={() => setHovered(false)}
    >
      <MeshDistortMaterial
        color={hovered ? "#c084fc" : "#7c3aed"}
        attach="material"
        distort={0.42}
        speed={hovered ? 4.5 : 1.8}
        roughness={0.15}
        metalness={0.75}
        clearcoat={1.0}
        clearcoatRoughness={0.1}
      />
    </Sphere>
  );
}

function FloatingParticles() {
  const pointsRef = useRef<THREE.Points>(null);
  
  // Generate stable particle coordinates
  const count = 350;
  const positions = React.useMemo(() => {
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 8;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 8;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 8;
    }
    return pos;
  }, []);

  useFrame((state) => {
    if (!pointsRef.current) return;
    
    // Gently rotate the particle field
    pointsRef.current.rotation.y += 0.0008;
    pointsRef.current.rotation.x += 0.0003;
    
    // Slight shift based on mouse
    const x = state.pointer.x * 0.4;
    const y = state.pointer.y * 0.4;
    pointsRef.current.position.x = THREE.MathUtils.lerp(pointsRef.current.position.x, x, 0.05);
    pointsRef.current.position.y = THREE.MathUtils.lerp(pointsRef.current.position.y, y, 0.05);
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>
      <PointMaterial
        transparent
        color="#3b82f6"
        size={0.065}
        sizeAttenuation={true}
        depthWrite={false}
        opacity={0.7}
      />
    </points>
  );
}

export default function AgentCore3D() {
  return (
    <div className="w-full h-full min-h-[260px] relative cursor-pointer overflow-hidden rounded-2xl glass-premium">
      <Canvas camera={{ position: [0, 0, 4.5], fov: 55 }}>
        <ambientLight intensity={0.55} />
        <directionalLight position={[5, 8, 5]} intensity={1.8} />
        <pointLight position={[-5, -5, -5]} color="#8b5cf6" intensity={1.2} />
        <pointLight position={[5, -5, 5]} color="#3b82f6" intensity={1} />
        <AgentSphere />
        <FloatingParticles />
      </Canvas>
      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 pointer-events-none text-[10px] text-purple-300 font-semibold tracking-widest uppercase opacity-75 bg-black/40 px-3 py-1 rounded-full backdrop-blur-sm">
        DECISION ENGINE CORE
      </div>
    </div>
  );
}

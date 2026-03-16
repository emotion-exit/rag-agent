<template>
  <div
    class="relative mt-8 flex lg:mt-0 lg:px-0 lg:pb-4 lg:pl-[calc(var(--section-gap)/2)]">
    <i
      class="flex h-8 w-8 place-items-center place-content-center text-(--color-text) lg:absolute lg:left-[-26px] lg:top-[calc(50%-25px)] lg:h-[50px] lg:w-[50px] lg:rounded-lg lg:border lg:border-(--color-border) lg:bg-(--color-background)">
      <slot name="icon"></slot>
    </i>
    <div class="ml-4 flex-1 before:hidden lg:ml-0">
      <h3 class="mb-1.5 text-[1.2rem] font-medium text-(--color-heading)">
        <slot name="heading"></slot>
      </h3>
      <slot></slot>
    </div>
  </div>
</template>

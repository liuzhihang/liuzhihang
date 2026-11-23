# Profile assets

- The hero and project thumbnails are original illustrations, not product screenshots. The Doc View thumbnail uses the [published quick-start example](https://github.com/liuzhihang/doc-view/blob/v1.7.2/docs/user-guide/index.md#三步生成第一份文档).
- The contribution grid is generated from the dates and levels visible on the public GitHub profile. No private account data or personal token is fetched. Color reflects level, not an exact commit count.
- To refresh locally: `python3 scripts/render_arcade.py --username liuzhihang --output assets/profile`. The workflow refreshes weekly from the default branch. A failed fetch does not replace the last successful images. The renderer can also use previously saved public calendar HTML.
- The footer is the only animation. When the operating system requests reduced motion, it shows the grid without animated characters.
